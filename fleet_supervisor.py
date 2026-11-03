#!/usr/bin/env python3
"""Bounded self-hosted Hunter/Praetor fleet supervisor.

Do not run as a perpetually restarted GitHub-hosted Actions workload.
Run only on an owned/authorized machine for sustained computation.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import tarfile
import tempfile
import time
import urllib.parse
import urllib.request

UTC = dt.timezone.utc
FILES = ("state.tsv", "FOUND.tsv", "VERIFIED.tsv", "gaps.tsv", "jobs.tsv",
         "hunt.log", "records.txt")


def utcnow() -> str:
    return dt.datetime.now(UTC).isoformat(timespec="seconds")


def read_json(path: Path, default: dict | None = None) -> dict:
    try:
        item = json.loads(path.read_text())
        return item if isinstance(item, dict) else (default or {})
    except (OSError, ValueError):
        return default or {}


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def append_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(payload, separators=(",", ":")) + "\n")
        f.flush()


def parse_found(path: Path) -> dict[str, tuple[int, float]]:
    """One line: gap TAB merit TAB start_expression [TAB metadata]."""
    findings: dict[str, tuple[int, float]] = {}
    if not path.exists():
        return findings
    with path.open(errors="replace") as f:
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) < 3:
                continue
            try:
                gap, merit = int(p[0]), float(p[1])
            except ValueError:
                continue
            if gap > 0 and merit > 0 and p[2]:
                findings[p[2]] = (gap, merit)
    return findings


def verified_expressions(path: Path) -> set[str]:
    good: set[str] = set()
    if not path.exists():
        return good
    with path.open(errors="replace") as f:
        for line in f:
            p = line.rstrip("\n").split("\t")
            # Hunter verification rows are 'gap\t-\texpression\tOK'.
            if len(p) >= 4 and p[3].strip() == "OK":
                good.add(p[2])
    return good


def summarize(root: Path, before_found: set[str] | None = None,
              before_verified: set[str] | None = None) -> dict:
    entries = parse_found(root / "FOUND.tsv")
    ok = verified_expressions(root / "VERIFIED.tsv")
    confirmed = [(gap, merit, expr) for expr, (gap, merit) in entries.items() if expr in ok]
    confirmed.sort(key=lambda row: (-row[1], -row[0]))
    initial_f = before_found or set()
    initial_v = before_verified or set()
    new_ok = [expr for expr in entries if expr in ok and expr not in initial_v]
    new_confirmed = [entries[expr][1] for expr in new_ok]
    return {
        "found_total": len(entries),
        "found_new": len(set(entries) - initial_f),
        "independently_verified_total": len(confirmed),
        "independently_verified_new": len(new_ok),
        "verified_merit_25_new": sum(m >= 25 for m in new_confirmed),
        "verified_merit_30_new": sum(m >= 30 for m in new_confirmed),
        "verified_merit_40_new": sum(m >= 40 for m in new_confirmed),
        "verified_merit_25_total": sum(m >= 25 for _, m, _ in confirmed),
        "verified_merit_30_total": sum(m >= 30 for _, m, _ in confirmed),
        "verified_merit_40_total": sum(m >= 40 for _, m, _ in confirmed),
        # NEVER expose full expressions in a public issue/checkpoint.
        "top_verified": [{"gap": g, "merit": round(m, 4)} for g, m, _ in confirmed[:5]],
    }


def api(port: int, path: str, form: dict | None = None, timeout: float = 20) -> dict:
    body = urllib.parse.urlencode(form).encode() if form is not None else None
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", data=body, timeout=timeout) as response:
        data = json.loads(response.read())
    if not isinstance(data, dict):
        raise RuntimeError(f"Hunter returned unexpected JSON from {path}")
    return data


def backup(root: Path, data: Path, campaign: int, metadata: dict) -> Path:
    out = data / "backups"
    out.mkdir(parents=True, exist_ok=True)
    target = out / f"campaign-{campaign:04d}.tar.gz"
    with tempfile.NamedTemporaryFile(dir=out, prefix=".backup-", suffix=".tar.gz", delete=False) as f:
        tmp = Path(f.name)
    try:
        with tarfile.open(tmp, mode="w:gz") as tf:
            for name in FILES:
                if (root / name).is_file():
                    tf.add(root / name, arcname=name, recursive=False)
            manifest = out / f"campaign-{campaign:04d}.json"
            atomic_json(manifest, metadata)
            tf.add(manifest, arcname="manifest.json")
        os.replace(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)
    return target


def github_report(repo: str, token: str, issue: int | None, summary: dict,
                  progress: dict, create: bool) -> int | None:
    """Opt-in, aggregate-only issue body update. No candidate prime expressions."""
    if not token:
        return issue
    title = "Hunter self-hosted fleet harvest"
    rows = [f"- gap {item['gap']:,}, merit {item['merit']:.4f}" for item in summary["top_verified"]]
    body = "\n".join([
        "### hunter fleet harvest (self-hosted)",
        f"last update: {utcnow()}",
        f"campaign: {progress['campaign']} | workers: {progress['cores']}",
        f"phase: {progress['phase']}",
        f"budget reserved: {progress['budget_reserved']:.2f}/{progress['budget_max']:.2f} worker-hours",
        f"found: {summary['found_total']} (+{summary['found_new']} campaign)",
        f"independently checked OK: {summary['independently_verified_total']} (+{summary['independently_verified_new']} campaign)",
        f"verified merit >=25: {summary['verified_merit_25_total']} (+{summary['verified_merit_25_new']} campaign)",
        f"verified merit >=30: {summary['verified_merit_30_total']} (+{summary['verified_merit_30_new']} campaign)",
        f"verified merit >=40: {summary['verified_merit_40_total']} (+{summary['verified_merit_40_new']} campaign)",
        "", "top verified gaps (no unpublished expressions):",
        *(rows or ["- none yet"]),
        "", "These are local table comparisons, not necessarily current world records or primality certificates."
    ])
    method = "POST" if issue is None and create else "PATCH"
    if issue is None and not create:
        return None
    url = f"https://api.github.com/repos/{repo}/issues" + (f"/{issue}" if issue is not None else "")
    req = urllib.request.Request(url, method=method,
       data=json.dumps({"title": title, "body": body} if method == "POST" else {"body": body}).encode(),
       headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                "Content-Type": "application/json", "User-Agent": "hunter-fleet",
                "X-GitHub-Api-Version": "2022-11-28"})
    with urllib.request.urlopen(req, timeout=20) as response:
        value = json.loads(response.read())
    return int(value["number"])


def stop_group(proc: subprocess.Popen, grace: int = 20) -> None:
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait(timeout=10)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cores", type=int, default=min(10, os.cpu_count() or 1))
    p.add_argument("--campaign-hours", type=float, default=5)
    p.add_argument("--max-campaigns", type=int, default=2)
    p.add_argument("--budget-core-hours", type=float, default=100,
                   help="hard total reservation budget across subsequent invocations")
    p.add_argument("--cooldown-minutes", type=float, default=10)
    p.add_argument("--checkpoint-minutes", type=float, default=15)
    p.add_argument("--port", type=int, default=8766)
    p.add_argument("--arms", default="6007.210,6007.2310,8009.210,8009.2310")
    p.add_argument("--job-seconds", type=int, default=60)
    p.add_argument("--publish", action="store_true", help="opt in to update an issue on github")
    p.add_argument("--github-repo", default="beerooyay/hunter")
    p.add_argument("--dry-run", action="store_true", help="show plan and budgets without launching hunter")
    p.add_argument("--status", action="store_true", help="show last harvest and exit")
    args = p.parse_args()
    if args.cores < 1 or args.cores > (os.cpu_count() or 1):
        p.error("--cores must be between 1 and detected CPUs; avoid oversubscription")
    if args.campaign_hours <= 0 or args.budget_core_hours <= 0 or args.max_campaigns < 1:
        p.error("positive budgets and campaign count required")
    if args.cooldown_minutes < 0 or args.checkpoint_minutes < 0.1 or args.job_seconds < 20:
        p.error("invalid time settings")
    if not (1024 <= args.port <= 65535):
        p.error("invalid port")
    return args


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parent
    data = root / "fleet"
    ledger_path = data / "budget.json"
    state = read_json(ledger_path, {"reserved_core_hours": 0.0, "campaigns_reserved": 0})
    if args.status:
        print(json.dumps({"budget": state, "latest": read_json(data / "latest.json")}, indent=2))
        return 0
    max_cores = args.budget_core_hours
    used = float(state.get("reserved_core_hours", 0))
    remaining = max(0.0, max_cores - used)
    plan = []
    for i in range(args.max_campaigns):
        if remaining < args.cores / 6: # skip segments shorter than 10 minutes
            break
        hours = min(args.campaign_hours, remaining / args.cores)
        plan.append(round(hours, 5))
        remaining -= hours * args.cores
    print(json.dumps({"cores": args.cores, "planned_campaign_hours": plan,
                      "remaining_budget_before": max(0.0, max_cores - used),
                      "budget_ceiling_worker_hours": max_cores,
                      "self_hosted_only": True}, indent=2), flush=True)
    if args.dry_run or not plan:
        return 0
    if not (root / "hunter").exists():
        raise SystemExit("./hunter binary not built; run ./build.sh first")
    if not (root / "records.txt").exists() or (root / "records.txt").stat().st_size < 1000000:
        raise SystemExit("records.txt missing/incomplete; prepare a current table first")
    if (data / "STOP").exists():
        raise SystemExit("fleet/STOP exists; remove manually to start a new approved campaign")
    try:
        api(args.port, "/api/status", timeout=1)
    except (OSError, ValueError):
        pass
    else:
        raise SystemExit(f"port {args.port} already has a Hunter server; refusing to interfere")
    data.mkdir(exist_ok=True)
    # flock prevents a second local supervisor from launching duplicate jobs.
    import fcntl
    lock = (data / "fleet.lock").open("w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit("another fleet supervisor owns fleet/fleet.lock")
    token = os.environ.get("GH_TOKEN", "") if args.publish else ""
    issue = read_json(data / "issue.json").get("number") if args.publish else None
    if args.publish and not token:
        print("warning: --publish set without GH_TOKEN; only local 15-minute harvests", flush=True)
    with (data / "server.log").open("a") as logs:
        server = subprocess.Popen([str(root / "hunter"), "serve", str(args.port)], cwd=root,
                                  stdout=logs, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            for _ in range(60):
                if server.poll() is not None:
                    raise RuntimeError("Hunter server exited during startup")
                try:
                    if api(args.port, "/api/status", timeout=2).get("engine") == "praetor":
                        break
                except (OSError, ValueError):
                    time.sleep(0.5)
            else:
                raise RuntimeError("Hunter server failed to start")
            for index, hours in enumerate(plan, start=1):
                if (data / "STOP").exists():
                    break
                state = read_json(ledger_path, {"reserved_core_hours": 0.0, "campaigns_reserved": 0})
                campaign_id = int(state.get("campaigns_reserved", 0)) + 1
                reservation = args.cores * hours
                if float(state.get("reserved_core_hours", 0)) + reservation > args.budget_core_hours + 1e-6:
                    raise RuntimeError("hard cumulative budget guard failed")
                # Conservative precharge. Interrupted campaigns cannot silently refund compute.
                state["reserved_core_hours"] = float(state.get("reserved_core_hours", 0)) + reservation
                state["campaigns_reserved"] = campaign_id
                state["updated_utc"] = utcnow()
                atomic_json(ledger_path, state)
                initial_found = set(parse_found(root / "FOUND.tsv"))
                initial_ok = verified_expressions(root / "VERIFIED.tsv")
                start_response = api(args.port, "/api/start", {
                    "cores": args.cores, "hours": hours, "job": args.job_seconds,
                    "gpu": 0, "arms": args.arms
                })
                if not start_response.get("ok", False):
                    raise RuntimeError(f"Hunter did not start: {start_response}")
                print(f"campaign {campaign_id} started ({hours:.2f} hours; {args.cores} workers)", flush=True)
                append_jsonl(data / "campaigns.jsonl", {
                    "campaign": campaign_id, "started_utc": utcnow(), "planned_hours": hours,
                    "cores": args.cores, "event": "start"})
                start_time = time.monotonic()
                next_checkpoint = start_time
                try:
                    while True:
                        status = api(args.port, "/api/status")
                        if server.poll() is not None:
                            raise RuntimeError("Hunter server crashed: no automatic blind relaunch")
                        if time.monotonic() >= next_checkpoint:
                            summary = summarize(root, initial_found, initial_ok)
                            progress = {
                                "campaign": campaign_id, "cores": args.cores,
                                "phase": "searching" if status.get("running") else "finished",
                                "budget_reserved": state["reserved_core_hours"],
                                "budget_max": args.budget_core_hours, "timestamp": utcnow(),
                                "elapsed_hours": round((time.monotonic() - start_time) / 3600, 4),
                                "worker_status": len(status.get("workers", [])), "summary": summary}
                            atomic_json(data / "latest.json", progress)
                            append_jsonl(data / "checkpoints.jsonl", progress)
                            print("harvest", json.dumps(progress, separators=(",", ":")), flush=True)
                            if args.publish and token:
                                try:
                                    issue = github_report(args.github_repo, token, issue,
                                                          summary, progress, True)
                                    atomic_json(data / "issue.json", {
                                        "number": issue, "repo": args.github_repo})
                                except Exception as exc:
                                    print("github report failed (hunter continues):", repr(exc), flush=True)
                            next_checkpoint = time.monotonic() + args.checkpoint_minutes * 60
                        if (not status.get("running") or (data / "STOP").exists()
                            or time.monotonic()-start_time >= hours*3600):
                            break
                        time.sleep(min(15, max(0.5, next_checkpoint - time.monotonic())))
                finally:
                    status = api(args.port, "/api/status")
                    if status.get("running") and not status.get("stopping"):
                        api(args.port, "/api/stop")
                    limit = time.monotonic() + max(300, args.job_seconds * 3)
                    while time.monotonic() < limit:
                        status = api(args.port, "/api/status")
                        if not status.get("running"):
                            break
                        time.sleep(2)
                    if status.get("running"):
                        print("graceful stop timed out; requesting immediate stop", flush=True)
                        api(args.port, "/api/stop", {"now": 1})
                        time.sleep(5)
                    # Independently verify any pending candidate findings.
                    try:
                        api(args.port, "/api/verify", {})
                        t_verify = time.monotonic() + 180
                        while time.monotonic() < t_verify:
                            check = api(args.port, "/api/status")
                            if int(check.get("tasks", {}).get("verifying", 0)) == 0:
                                break
                            time.sleep(3)
                    except Exception as exc:
                        print("verification request failed:", repr(exc), flush=True)
                    summary = summarize(root, initial_found, initial_ok)
                    yield_rates = {
                        f"verified_merit_{tier}_per_reserved_worker_hour":
                        round(summary[f"verified_merit_{tier}_new"] / reservation, 6)
                        for tier in (25, 30, 40)
                    }
                    metadata = {
                        "campaign": campaign_id, "start_planned_hours": hours,
                        "actual_wall_hours": round((time.monotonic()-start_time)/3600, 4),
                        "reserved_worker_hours": reservation, "cores": args.cores,
                        "completed_utc": utcnow(), "summary": summary,
                        "yield_rates": yield_rates,
                        "note": "probable prime checks are not primality certificates"}
                    archive = backup(root, data, campaign_id, metadata)
                    append_jsonl(data / "campaigns.jsonl", {
                        "event": "finish", **metadata, "backup": str(archive)})
                    print(f"campaign {campaign_id} finished; backup={archive}", flush=True)
                if index < len(plan) and not (data / "STOP").exists() and args.cooldown_minutes:
                    remaining_wait = args.cooldown_minutes * 60
                    while remaining_wait > 0 and not (data / "STOP").exists():
                        s = min(10, remaining_wait)
                        time.sleep(s)
                        remaining_wait -= s
        finally:
            try:
                status = api(args.port, "/api/status", timeout=3)
                if status.get("running"):
                    api(args.port, "/api/stop", {"now": 1}, timeout=3)
            except Exception:
                pass
            stop_group(server)
            lock.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
