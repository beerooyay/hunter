"""Bounded native Hunter campaign; all mutations stay in this job's directory.

Dispatch a fresh workflow to search new space. Retrying a run is deliberately
refused: a run/shard pair owns exactly one immutable multiplier reservation.
"""
from __future__ import annotations

import json
import os
import re
import signal
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import blitz_report as report

ROOT = Path(__file__).resolve().parent
UINT64_MAX = 2**64 - 1
RUN_STRIDE = 100_000_000
SHARD_WIDTH = 262_144
MAX_SHARD = 255
ALLOWED_ARMS = {"6007.2310", "8009.2310", "6007.210", "8009.210"}
HUNT_SECONDS = 18_000
DRAIN_SECONDS = 300
VERIFY_SECONDS = 600
POLL_SECONDS = 2


def namespace_bounds(run_id, shard, attempt=1):
    run_id = report.uint(run_id, "GITHUB_RUN_ID", positive=True)
    shard = report.uint(shard, "HUNTER_SHARD")
    attempt = report.uint(attempt, "GITHUB_RUN_ATTEMPT", positive=True)
    if attempt != 1:
        raise ValueError("retries reuse searched space; dispatch a fresh workflow instead (GITHUB_RUN_ATTEMPT must be 1)")
    if shard > MAX_SHARD:
        raise ValueError("HUNTER_SHARD must be in 0..255")
    start = run_id * RUN_STRIDE
    base = start + shard * SHARD_WIDTH + 1
    end = base + SHARD_WIDTH
    if start > UINT64_MAX or base > UINT64_MAX or end > UINT64_MAX:
        raise ValueError("multiplier reservation exceeds uint64; dispatch is unsafe")
    return base, end


def make_config(env, cpu_count=None):
    run_id = report.uint(env["GITHUB_RUN_ID"], "GITHUB_RUN_ID", positive=True)
    shard = report.uint(env["HUNTER_SHARD"], "HUNTER_SHARD")
    attempt = report.uint(env.get("GITHUB_RUN_ATTEMPT", "1"), "GITHUB_RUN_ATTEMPT", positive=True)
    base, end = namespace_bounds(run_id, shard, attempt)
    arm = env["HUNTER_ARM"]
    if not re.fullmatch(r"[0-9]+\.[0-9]+", arm):
        raise ValueError("HUNTER_ARM must name one P.d family")
    p, d = (report.uint(v, n, positive=True) for v, n in zip(arm.split("."), ("P", "d")))
    if f"{p}.{d}" not in ALLOWED_ARMS:
        raise ValueError("HUNTER_ARM is not an approved production family")
    variant = env.get("HUNTER_VARIANT", "baseline")
    if variant not in ("baseline", "half-cutoff"):
        raise ValueError("HUNTER_VARIANT must be baseline or half-cutoff")
    percent = 100 if variant == "baseline" else 50
    if "HUNTER_LAMBDA_PERCENT" in env and report.uint(env["HUNTER_LAMBDA_PERCENT"], "HUNTER_LAMBDA_PERCENT") != percent:
        raise ValueError("HUNTER_LAMBDA_PERCENT conflicts with the declared variant")
    seconds = report.uint(env.get("HUNTER_SECONDS", str(HUNT_SECONDS)), "HUNTER_SECONDS", positive=True)
    if seconds > HUNT_SECONDS:
        raise ValueError("HUNTER_SECONDS cannot exceed 18000")
    detected = os.cpu_count() if cpu_count is None else cpu_count
    available = min(62, max(1, detected or 1))
    cores = report.uint(env.get("HUNTER_CORES", str(available)), "HUNTER_CORES", positive=True)
    if cores > available:
        raise ValueError(f"HUNTER_CORES exceeds safe available count {available}")
    port = report.uint(env.get("HUNTER_PORT", "8765"), "HUNTER_PORT", positive=True)
    if port > 65535:
        raise ValueError("HUNTER_PORT exceeds 65535")
    return {"run_id": run_id, "attempt": attempt, "shard": shard, "base": base,
            "exclusive_end": end, "arm": f"{p}.{d}", "P": p, "d": d,
            "variant": variant, "lambda_percent": percent,
            "cores": cores, "seconds": seconds, "port": port,
            "sha": env.get("GITHUB_SHA", ""),
            "build_manifest_path": env.get("HUNTER_BUILD_MANIFEST", "build-manifest.json")}


def render_state(template_text, base):
    report.uint(base, "base", positive=True)
    rows, arms = [], set()
    for number, line in enumerate(template_text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) < 5 or not report.ARM.fullmatch(fields[0]):
            raise ValueError(f"invalid state template row {number}")
        p, d = report.uint(fields[1], "state P", True), report.uint(fields[2], "state d", True)
        if not fields[0].startswith(f"P{p}_d{d}_") or (p, d) in arms:
            raise ValueError(f"inconsistent or duplicate state arm at row {number}")
        arms.add((p, d))
        fields[4] = str(base)
        rows.append("\t".join(fields))
    if not rows:
        raise ValueError("state template has no arms")
    return "\n".join(rows) + "\n"


def validate_status(status, config, expect_running=False):
    """Fail closed on malformed status, wrong reservation, or unexpected workers."""
    if not isinstance(status, dict) or status.get("engine") != "praetor":
        raise RuntimeError("unexpected native status response")
    for field in ("running", "stopping", "range_exhausted"):
        if type(status.get(field)) is not bool:
            raise RuntimeError(f"native status missing boolean {field}")
    for field in ("now", "started", "ends", "cores"):
        if type(status.get(field)) is not int or not 0 <= status[field] <= UINT64_MAX:
            raise RuntimeError(f"invalid native status integer {field}")
    if status["cores"] != config["cores"]:
        raise RuntimeError("native core count differs from requested count")
    if report.uint(status.get("m_end", ""), "status m_end", True) != config["exclusive_end"]:
        raise RuntimeError("native multiplier cap was not applied")
    if status.get("lambda_percent") != config["lambda_percent"]:
        raise RuntimeError("native lambda override was not applied")
    for field in ("learned_lambda", "effective_lambda"):
        if field not in status:
            raise RuntimeError(f"native status missing {field}")
        report.merit_value(status[field])
    workers, tasks, arms = status.get("workers"), status.get("tasks"), status.get("arms")
    if not isinstance(workers, list) or not isinstance(tasks, dict) or not isinstance(arms, list):
        raise RuntimeError("native status missing workers/tasks/arms")
    verifying = tasks.get("verifying")
    if type(verifying) is not int or not 0 <= verifying <= 16:
        raise RuntimeError("invalid active verifier count")
    enabled = [(a.get("P"), a.get("d")) for a in arms if isinstance(a, dict) and a.get("on")]
    if enabled != [(config["P"], config["d"])]:
        raise RuntimeError("native active arms differ from the one assigned family")
    if len(workers) > config["cores"]:
        raise RuntimeError("native worker count exceeds allocated cores")
    if workers and not status["running"]:
        raise RuntimeError("native status has workers while the hunt is not running")
    for worker in workers:
        if not isinstance(worker, dict) or (worker.get("P"), worker.get("d")) != (config["P"], config["d"]):
            raise RuntimeError("worker belongs to an unassigned arm")
        m = report.uint(worker.get("m0", ""), "worker m0", True)
        count = report.uint(worker.get("M", ""), "worker M", True)
        if m < config["base"] or m >= config["exclusive_end"] or m + count > config["exclusive_end"]:
            raise RuntimeError("worker reservation escapes this shard")
    if expect_running and (not status["running"] or status["stopping"]) and not status["range_exhausted"]:
        raise RuntimeError("hunt stopped or paused unexpectedly before its deadline")
    return status


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def api(config, path, data=None, root=None):
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    with urllib.request.urlopen(f"http://127.0.0.1:{config['port']}{path}", data=body, timeout=15) as response:
        payload = response.read(8 * 1024 * 1024 + 1)
    if len(payload) > 8 * 1024 * 1024:
        raise RuntimeError("native response exceeds the bounded status size")
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise RuntimeError("native API returned a nonobject response")
    if path == "/api/status" and root is not None:
        # Preserve the actual JSON bytes, including full-width uint64 integers.
        report.atomic_text(Path(root) / "native-status.json", payload.decode("utf-8") + "\n")
    return value


def require_ok(value, action):
    if value.get("ok") is not True:
        raise RuntimeError(f"native {action} rejected: {value!r}")
    return value


def spawn_owned(args, root, output, env=None):
    with Path(output).open("ab", buffering=0) as handle:
        process = subprocess.Popen(args, cwd=root, env=env, stdout=handle,
                                   stderr=subprocess.STDOUT, start_new_session=True)
    process._hunter_owned_pgid = process.pid
    return process


def terminate_owned_group(process, timeout=10):
    """Stop only a process group this launcher created with start_new_session."""
    pgid = getattr(process, "_hunter_owned_pgid", None)
    if pgid is None:
        if process.poll() is not None:
            return
        if os.getpgid(process.pid) != process.pid:
            raise RuntimeError("refusing to stop a process that does not own its group")
        pgid = process.pid
    if pgid <= 1 or pgid == os.getpgrp() or pgid != process.pid:
        raise RuntimeError("refusing to signal an unowned process group")
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        pass
    # The leader can exit before its descendants; the whole owned group expires.
    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=5)


class TailMonitor:
    """Read only new complete raw lines and announce each actual >=25 gap once."""
    def __init__(self, root):
        self.root, self.offset, self.buffer, self.line = Path(root), 0, b"", 0
        self.seen = set()

    def poll(self):
        path = self.root / "gaps.tsv"
        if not path.exists():
            return
        if path.stat().st_size < self.offset:
            raise RuntimeError("gaps.tsv shrank during the campaign")
        with path.open("rb") as handle:
            handle.seek(self.offset)
            data = handle.read()
            self.offset = handle.tell()
        self.buffer += data
        lines = self.buffer.split(b"\n")
        self.buffer = lines.pop()
        for line in lines:
            self.line += 1
            row = report.parse_gap_line(line.decode("utf-8"), "gaps.tsv", self.line)
            if row is None or report.merit_value(row["merit"]) < 25 or report.key(row) in self.seen:
                continue
            self.seen.add(report.key(row))
            snapshot = report.scan_job(self.root)
            matches = [r for r in snapshot["candidates"] if report.key(r) == report.key(row)]
            state = matches[0]["verification_status"] if matches else "PENDING"
            print(f"HIGH_MERIT status={state} gap={row['gap']} m={row['m']} P={row['P']} d={row['d']} "
                  f"submission={report.submission_line(row)!r}", flush=True)


def checkpoint(root, phase):
    snapshot = report.write_job_report(root)
    metrics = snapshot["metrics"]
    print("checkpoint " + json.dumps({"at": utc_now(), "phase": phase,
          "actual_best": metrics["best_actual_merit"], "actual_ge25": metrics["tails"]["25"],
          "found": metrics["found"], "verified_found": metrics["found_verified"],
          "ready": metrics["ready"], "pending": metrics["pending"],
          "failed": metrics["failed"], "conflict": metrics["conflict"]}, sort_keys=True), flush=True)
    return snapshot


def settle(config, root, server, monitor, owned_verifiers):
    """Five-minute hunt drain followed by at most ten minutes for verification."""
    if server.poll() is not None:
        raise RuntimeError("native server exited before shutdown/verification grace")
    status = validate_status(api(config, "/api/status", root=root), config)
    if status["running"]:
        require_ok(api(config, "/api/stop", {"now": 0}), "graceful stop")
    drain_deadline = time.monotonic() + DRAIN_SECONDS
    next_checkpoint = 0
    while status["workers"] and time.monotonic() < drain_deadline:
        if server.poll() is not None:
            raise RuntimeError("native server crashed during job drain")
        monitor.poll()
        if time.monotonic() >= next_checkpoint:
            checkpoint(root, "drain")
            next_checkpoint = time.monotonic() + 60
        time.sleep(min(POLL_SECONDS, max(0, drain_deadline - time.monotonic())))
        status = validate_status(api(config, "/api/status", root=root), config)
    if status["workers"]:
        # This API signals only hunt workers. Existing verifier processes survive.
        require_ok(api(config, "/api/stop", {"now": 1}), "forced hunt stop")

    deadline, attempted, batches = time.monotonic() + VERIFY_SECONDS, set(), set()
    active = {}
    next_checkpoint = 0
    while time.monotonic() < deadline:
        if server.poll() is not None:
            raise RuntimeError("native server crashed during verification grace")
        status = validate_status(api(config, "/api/status", root=root), config)
        monitor.poll()
        for k, proc in list(active.items()):
            if proc.poll() is not None:
                print(f"priority_verifier_finished key={k!r} exit={proc.returncode}", flush=True)
                del active[k]
        snapshot = report.scan_job(root)
        if time.monotonic() >= next_checkpoint:
            checkpoint(root, "verification")
            next_checkpoint = time.monotonic() + 60
        native_active = status["tasks"]["verifying"]
        pending = [r for r in snapshot["candidates"] if r["verification_status"] == "PENDING"]
        high = [r for r in pending if report.merit_value(r["merit"]) >= 25 and report.key(r) not in attempted]
        if not status["workers"] and native_active == 0:
            # Native autoverification is idle, so these launches cannot duplicate
            # an active automatic verifier for the same expression.
            slots = min(config["cores"], 16) - len(active)
            for row in high[:max(0, slots)]:
                k = report.key(row)
                attempted.add(k)
                proc = spawn_owned([str(root / "hunter"), "verify", row["expression"], str(row["gap"])],
                                   root, root / "blitz-verifiers.log")
                owned_verifiers.append(proc)
                active[k] = proc
                print(f"priority_verify status=PENDING submission={report.submission_line(row)!r}", flush=True)
            # verify_pending() has no active-expression deduplication. Invoke it
            # only when BOTH native and directly owned verifiers are idle.
            remaining_found = tuple(sorted(report.key(r) for r in pending if r["reported_found"]))
            if not active and not high and remaining_found and remaining_found not in batches:
                batches.add(remaining_found)
                require_ok(api(config, "/api/verify", {}), "verify pending")
                time.sleep(min(POLL_SECONDS, max(0, deadline - time.monotonic())))
                continue
            if not active and not high and (not remaining_found or remaining_found in batches):
                break
        time.sleep(min(POLL_SECONDS, max(0, deadline - time.monotonic())))
    monitor.poll()
    return {"verification_finished_at": utc_now()}


def prepare_manifest(config, root):
    build_path = Path(config["build_manifest_path"])
    if not build_path.is_absolute():
        build_path = root / build_path
    build = json.loads(build_path.read_text())
    if not isinstance(build, dict):
        raise ValueError("build-manifest.json must contain an object")
    compiler_sha = next((build.get(k) for k in ("compiler_sha", "compiler_revision", "praetor_sha") if build.get(k)), None)
    if not isinstance(compiler_sha, str) or not re.fullmatch(r"[0-9a-fA-F]{40}", compiler_sha):
        raise ValueError("build manifest must identify the pinned compiler commit")
    sha = config["sha"] or subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    if not re.fullmatch(r"[0-9a-fA-F]{40}", sha):
        raise ValueError("campaign revision must be an exact git SHA")
    if build.get("hunter_sha") != sha:
        raise ValueError("shared build revision does not match this workflow revision")
    plan = build.get("matrix", {})
    if not isinstance(plan, dict) or not isinstance(plan.get("include"), list):
        raise ValueError("shared build manifest has no declared shard matrix")
    assigned = [item for item in plan["include"] if isinstance(item, dict) and item.get("shard") == config["shard"]]
    if len(assigned) != 1 or assigned[0].get("arm") != config["arm"] or assigned[0].get("variant") != config["variant"]:
        raise ValueError("this shard arm/variant differs from the predeclared shared matrix")
    records = root / "records.txt"
    if not records.is_file() or records.stat().st_size < 1_000_000:
        raise ValueError("the pinned records.txt table is missing or too small")
    records_hash = report.sha256(records)
    binary_hash = report.sha256(root / "hunter")
    for field, actual in (("records_sha256", records_hash), ("hunter_binary_sha256", binary_hash)):
        expected = build.get(field)
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected) or expected != actual:
            raise ValueError(f"shared build manifest {field} does not match this job's input")
    return {"schema_version": 1, "run_id": str(config["run_id"]), "attempt": str(config["attempt"]),
            "shard": str(config["shard"]), "sha": sha, "arm": config["arm"],
            "variant": config["variant"], "base": str(config["base"]),
            "exclusive_end": str(config["exclusive_end"]), "namespace_width": str(SHARD_WIDTH),
            "lambda_percent": config["lambda_percent"], "cores": config["cores"],
            "hunt_seconds_requested": config["seconds"], "drain_seconds_max": DRAIN_SECONDS,
            "verification_seconds_max": VERIFY_SECONDS, "created_at": utc_now(),
            "compiler_revision": compiler_sha, "build_manifest": build,
            "build_manifest_sha256": report.sha256(build_path),
            "public_record_source_sha256": build.get("source_sha256"),
            "raw_record_table_sha256": records_hash, "record_table_bytes": records.stat().st_size,
            "hunter_binary_sha256": binary_hash, "outcome": "prepared"}


def run_campaign(config, root=ROOT):
    root = Path(root).resolve()
    for name in ("FOUND.tsv", "VERIFIED.tsv", "gaps.tsv", "jobs.tsv", "job-reservations.tsv", "blitz-manifest.json"):
        path = root / name
        if path.exists() and path.stat().st_size:
            raise ValueError(f"{name} already contains results; use a fresh workflow workspace")
    state = render_state((root / "cloud-state-template.tsv").read_text(), config["base"])
    if not any(line.startswith(f"P{config['P']}_d{config['d']}_") for line in state.splitlines()):
        raise ValueError("assigned arm is absent from the state template")
    manifest = prepare_manifest(config, root)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", config["port"]))
    report.atomic_text(root / "state.tsv", state)
    report.write_json(root / "blitz-manifest.json", manifest)
    env = dict(os.environ, HUNTER_M_END=str(config["exclusive_end"]),
               HUNTER_LAMBDA_PERCENT=str(config["lambda_percent"]), HUNTER_NO_OPEN="1", HUNTER_GPU="0")
    for diagnostic in ("HUNT_DRY", "HUNT_MASK_REFERENCE"):
        env.pop(diagnostic, None)
    server, owned_verifiers, monitor = None, [], TailMonitor(root)
    error, started = None, False
    try:
        server = spawn_owned([str(root / "hunter"), "serve", str(config["port"])],
                             root, root / "native-server.log", env)
        startup_deadline = time.monotonic() + 60
        while True:
            if server.poll() is not None:
                raise RuntimeError(f"native server exited during startup: {server.returncode}")
            try:
                api(config, "/api/status", root=root)
                break
            except (OSError, ValueError):
                if time.monotonic() >= startup_deadline:
                    raise RuntimeError("native server startup timed out")
                time.sleep(.5)
        require_ok(api(config, "/api/start", {"cores": config["cores"], "hours": "5",
                                             "job": "60", "gpu": "0", "arms": config["arm"]}), "start")
        started = True
        manifest.update(outcome="running", hunt_started_at=utc_now())
        report.write_json(root / "blitz-manifest.json", manifest)
        print("campaign " + json.dumps(manifest, sort_keys=True), flush=True)
        deadline, next_checkpoint = time.monotonic() + config["seconds"], 0
        while time.monotonic() < deadline:
            if server.poll() is not None:
                raise RuntimeError(f"native server crashed: {server.returncode}")
            remaining = deadline - time.monotonic()
            status = validate_status(api(config, "/api/status", root=root), config)
            monitor.poll()
            if time.monotonic() >= next_checkpoint:
                checkpoint(root, "hunt")
                next_checkpoint = time.monotonic() + 60
            if status["range_exhausted"]:
                manifest["stop_reason"] = "reserved multiplier range exhausted"
                break
            if not status["running"] or status["stopping"]:
                if remaining > 3 or status["now"] < status["ends"]:
                    raise RuntimeError("unexpected early native pause")
                break
            time.sleep(min(POLL_SECONDS, max(0, deadline - time.monotonic())))
        manifest.setdefault("stop_reason", "configured hunt deadline")
    except BaseException as exc:
        error = exc
        manifest["error"] = f"{type(exc).__name__}: {exc}"
        print("campaign_error " + manifest["error"], flush=True)
    finally:
        manifest["hunt_stop_requested_at"] = utc_now()
        # Export before waiting as well as after: interruption must leave pending
        # evidence visible, with no assertion that unfinished checks succeeded.
        try:
            checkpoint(root, "stopping")
        except Exception as exc:
            print(f"report_error {exc}", flush=True)
            error = error or exc
        if server is not None and started:
            try:
                manifest.update(settle(config, root, server, monitor, owned_verifiers))
            except BaseException as exc:
                print(f"shutdown_error {type(exc).__name__}: {exc}", flush=True)
                error = error or exc
        for process in owned_verifiers + ([server] if server else []):
            try:
                terminate_owned_group(process)
            except Exception as exc:
                print(f"owned_cleanup_error {exc}", flush=True)
                error = error or exc
        manifest.update(finished_at=utc_now(), outcome="failed" if error else "completed")
        if error:
            manifest["error"] = f"{type(error).__name__}: {error}"
        report.write_json(root / "blitz-manifest.json", manifest)
        final = checkpoint(root, "final")
        if final["error_count"]:
            error = error or RuntimeError(f"artifact parsing found {final['error_count']} issue(s)")
            manifest.update(outcome="failed", error=str(error))
            report.write_json(root / "blitz-manifest.json", manifest)
            report.write_job_report(root)
    if error:
        raise RuntimeError(str(error)) from error
    return final


def main():
    def interrupted(signum, frame):
        raise KeyboardInterrupt(f"received signal {signum}")
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    try:
        # Validate attempts and arithmetic before any write or child process.
        run_campaign(make_config(os.environ))
    except (Exception, KeyboardInterrupt) as exc:
        print(f"blitz failed: {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
