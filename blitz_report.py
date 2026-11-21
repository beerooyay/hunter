"""Lossless, standard-library reporting for native Hunter artifacts.

An OK is an independent probable-prime/consecutive-gap check, not acceptance as
a formal record. The raw native merit is column 9 (zero based); column 10 is the
old record. No reporter writes to FOUND.tsv or VERIFIED.tsv.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path

UINT64_MAX = 2**64 - 1
TAILS = (20, 22, 24, 25, 26, 27, 28, 29)
EXPR = re.compile(r"([0-9]+)\*([0-9]+)#/([0-9]+)-([0-9]+)")
ARM = re.compile(r"P([0-9]+)_d([0-9]+)_L[0-9a-zA-Z.+-]+")
CAVEAT = (
    "READY requires FOUND.tsv plus an explicit, matching independent verifier OK "
    "for this exact gap and expression. This is a candidate improvement against "
    "the campaign's pinned table, not a primality proof or formal acceptance. "
    "Compare READY with the current public table before submitting: queued waves "
    "can span a day and the pinned table can become stale. Raw high-merit gaps "
    "are retained separately even when they are not record improvements. "
    "PENDING, FAILED, and CONFLICT must not be submitted as verified."
)


def uint(text, name, positive=False):
    value = str(text)
    if not re.fullmatch(r"[0-9]+", value):
        raise ValueError(f"invalid {name}: {value!r}")
    number = int(value)
    if number > UINT64_MAX or number < (1 if positive else 0):
        raise ValueError(f"{name} outside uint64 range")
    return number


def merit_value(text):
    try:
        value = Decimal(str(text))
    except InvalidOperation as exc:
        raise ValueError("invalid merit") from exc
    if not value.is_finite() or value < 0:
        raise ValueError("merit must be finite and nonnegative")
    return value


def expression_parts(expression):
    match = EXPR.fullmatch(re.sub(r"\s+", "", expression))
    if not match:
        raise ValueError("invalid native prime expression")
    m, p, d, left = (uint(v, n, positive=i < 3) for i, (v, n) in
                      enumerate(zip(match.groups(), ("m", "P", "d", "left"))))
    return {"expression": f"{m}*{p}#/{d}-{left}", "m": str(m),
            "P": p, "d": d, "left": left}


def candidate(gap, merit, expression, source, line_number):
    return {"gap": uint(gap, "gap", positive=True),
            "merit": str(merit_value(merit)), **expression_parts(expression),
            "source": str(source), "line": line_number}


def parse_gap_line(line, source="", line_number=0):
    """Return a completed actual gap, None for comments/incomplete work.

    Raises ValueError for malformed data. A high old-record column is never a
    candidate. The right and left distances must agree with the reported gap.
    """
    if not line.strip() or line.lstrip().startswith("#"):
        return None
    fields = line.rstrip("\r\n").split("\t")
    if len(fields) < 10:
        raise ValueError("gaps.tsv row has fewer than 10 fields")
    match = ARM.fullmatch(fields[0])
    if not match or fields[5] not in ("0", "1"):
        raise ValueError("invalid raw arm or completion marker")
    gap = uint(fields[8], "gap")
    if fields[5] == "0" or gap == 0:
        return None
    m = uint(fields[1], "m", positive=True)
    p, d = (uint(v, n, positive=True) for v, n in zip(match.groups(), ("P", "d")))
    left, right = uint(fields[6], "left"), uint(fields[7], "right")
    if left + right != gap:
        raise ValueError("gap does not equal left plus right")
    row = candidate(gap, fields[9], f"{m}*{p}#/{d}-{left}", source, line_number)
    row.update(raw_complete=True, raw_record_hit=len(fields) > 15 and fields[15] == "1")
    if len(fields) > 10:
        row["previous_record_merit"] = fields[10]
    return row


def parse_found_line(line, source="", line_number=0):
    if not line.strip() or line.lstrip().startswith("#"):
        return None
    fields = line.rstrip("\r\n").split("\t")
    if len(fields) < 3:
        raise ValueError("FOUND.tsv row has fewer than 3 fields")
    row = candidate(fields[0], fields[1], fields[2], source, line_number)
    row["reported_found"] = True
    row["metadata"] = fields[3:]
    return row


def parse_verified_line(line, source="", line_number=0):
    if not line.strip() or line.lstrip().startswith("#"):
        return None
    fields = line.rstrip("\r\n").split("\t")
    if len(fields) < 4 or fields[3] not in ("OK", "FAILED"):
        raise ValueError("VERIFIED.tsv requires an explicit OK or FAILED")
    return {"gap": uint(fields[0], "gap", positive=True),
            **expression_parts(fields[2]), "verification_status": fields[3],
            "source": str(source), "line": line_number}


def key(row):
    return row["gap"], row["expression"]


def sort_candidates(rows):
    return sorted(rows, key=lambda r: (-merit_value(r["merit"]), r["gap"], r["expression"]))


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def atomic_text(path, text):
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def write_json(path, value):
    atomic_text(path, json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def verification_status(rows):
    statuses = {row["verification_status"] for row in rows}
    if statuses == {"OK"}:
        return "OK"
    if statuses == {"FAILED"}:
        return "FAILED"
    if statuses:
        return "CONFLICT"
    return "PENDING"


def scan_job(directory):
    """Independently parse raw evidence, including jobs with no FOUND.tsv."""
    directory = Path(directory)
    errors, error_count = [], 0
    files, manifest, native_status = {}, {}, {}
    for name in ("gaps.tsv", "FOUND.tsv", "VERIFIED.tsv", "jobs.tsv", "state.tsv",
                 "native-status.json", "blitz-manifest.json", "build-manifest.json",
                 "job-reservations.tsv"):
        path = directory / name
        if path.is_file():
            files[name] = {"sha256": sha256(path), "bytes": path.stat().st_size}

    def error(name, line, message):
        nonlocal error_count
        error_count += 1
        if len(errors) < 100:
            errors.append({"source": name, "line": line, "error": message})

    for name, target in (("blitz-manifest.json", manifest), ("native-status.json", native_status)):
        if (directory / name).is_file():
            try:
                loaded = json.loads((directory / name).read_text())
                if not isinstance(loaded, dict):
                    raise ValueError("expected JSON object")
                target.update(loaded)
            except (ValueError, OSError) as exc:
                error(name, 0, str(exc))

    def parsed(name, parser):
        path = directory / name
        if not path.is_file():
            return
        with path.open(encoding="utf-8", errors="replace") as handle:
            for number, line in enumerate(handle, 1):
                if not line.endswith("\n"):
                    error(name, number, "unfinished final line ignored")
                    continue
                try:
                    row = parser(line, name, number)
                except (ValueError, IndexError) as exc:
                    error(name, number, str(exc))
                    continue
                if row:
                    row["source_sha256"] = files[name]["sha256"]
                    yield row

    raw, raw_rows, completed_rows, prp_tests = {}, 0, 0, 0
    gaps_path = directory / "gaps.tsv"
    if gaps_path.is_file():
        with gaps_path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if line.strip() and not line.lstrip().startswith("#"):
                    raw_rows += 1
                    f = line.rstrip("\r\n").split("\t")
                    if len(f) > 12:
                        try:
                            prp_tests += uint(f[11], "PRP right") + uint(f[12], "PRP left")
                        except ValueError:
                            pass
    for row in parsed("gaps.tsv", parse_gap_line):
        completed_rows += 1
        raw.setdefault(key(row), []).append(row)
    found, verified = {}, {}
    for row in parsed("FOUND.tsv", parse_found_line):
        found.setdefault(key(row), []).append(row)
    for row in parsed("VERIFIED.tsv", parse_verified_line):
        verified.setdefault(key(row), []).append(row)

    all_raw = [rows[0] for rows in raw.values()]
    high_keys = {k for k, rows in raw.items() if merit_value(rows[0]["merit"]) >= 20}
    candidates = []
    for k in set(found) | high_keys:
        evidence = raw.get(k, []) + found.get(k, [])
        # Prefer the actual raw merit, preserving conflicting evidence for review.
        row = dict(evidence[0])
        merits = {merit_value(r["merit"]) for r in evidence}
        checks = verified.get(k, [])
        state = verification_status(checks)
        if len(merits) > 1:
            error("candidate", 0, f"inconsistent merits for {k!r}")
            state = "CONFLICT"
        row.update(verification_status=state, reported_found=k in found,
                   raw_complete=k in raw, high_merit_raw=k in high_keys,
                   evidence=evidence, verification_evidence=checks)
        candidates.append(row)
    candidates = sort_candidates(candidates)
    status_counts = Counter(row["verification_status"] for row in candidates)
    status_arms = native_status.get("arms", [])
    if not isinstance(status_arms, list):
        error("native-status.json", 0, "arms must be an array")
        status_arms = []
    active_arms = [arm for arm in status_arms if isinstance(arm, dict) and arm.get("on")]
    core_hours = Decimal(0)
    for arm in active_arms:
        try:
            core_hours += merit_value(arm.get("coreh", 0))
        except ValueError as exc:
            error("native-status.json", 0, f"invalid coreh: {exc}")
    metrics = {
        "raw_rows": raw_rows, "completed_rows": completed_rows, "unique_completed": len(raw),
        "best_actual_merit": str(max((merit_value(r["merit"]) for r in all_raw), default=Decimal(0))),
        "tails": {str(t): sum(merit_value(r["merit"]) >= t for r in all_raw) for t in TAILS},
        "prp_tests_logged": prp_tests, "found": len(found), "candidates": len(candidates),
        "high_merit_raw": len(high_keys),
        "ready": sum(r["verification_status"] == "OK" and r["reported_found"] for r in candidates),
        "independently_ok": status_counts["OK"],
        "verified_high_merit": sum(r["verification_status"] == "OK" and r["high_merit_raw"] for r in candidates),
        "pending": status_counts["PENDING"], "failed": status_counts["FAILED"],
        "conflict": status_counts["CONFLICT"],
        "found_verified": sum(verification_status(verified.get(k, [])) == "OK" for k in found),
        "orphan_verification_keys": len(set(verified) - set(found) - set(raw)),
        "logged_core_hours": float(core_hours),
        "lambda": native_status.get("lambda"),
        "learned_lambda": native_status.get("learned_lambda"),
        "effective_lambda": native_status.get("effective_lambda"),
        "lambda_percent": native_status.get("lambda_percent", manifest.get("lambda_percent")),
    }
    return {"schema_version": 1, "directory": str(directory), "caveat": CAVEAT,
            "manifest": manifest, "native_status": native_status, "files": files,
            "metrics": metrics, "candidates": candidates,
            "error_count": error_count, "errors": errors}


def submission_line(row):
    return f"{row['gap']} {row['merit']} {row['expression']}"


def tsv(rows):
    header = "# gap\tmerit\texpression\tverification_status\treported_found\n"
    return header + "".join(
        f"{r['gap']}\t{r['merit']}\t{r['expression']}\t{r['verification_status']}\t{int(r.get('reported_found', False))}\n"
        for r in sort_candidates(rows)
    )


def write_exports(directory, candidates):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    groups = {
        "READY.tsv": [r for r in candidates if r["verification_status"] == "OK" and r.get("reported_found")],
        "PENDING.tsv": [r for r in candidates if r["verification_status"] != "OK"],
        "FAILED.tsv": [r for r in candidates if r["verification_status"] in ("FAILED", "CONFLICT")],
        "HIGH_MERIT.tsv": [r for r in candidates if r.get("high_merit_raw")],
        "VERIFIED_HIGH_MERIT.tsv": [r for r in candidates if r.get("high_merit_raw") and r["verification_status"] == "OK"],
    }
    for name, rows in groups.items():
        atomic_text(directory / name, tsv(rows))
    ready = "".join(submission_line(row) + "\n" for row in groups["READY.tsv"])
    atomic_text(directory / "READY.txt", ready)
    write_json(directory / "blitz-candidates.json", candidates)


def write_job_report(directory):
    report = scan_job(directory)
    write_exports(directory, report["candidates"])
    write_json(Path(directory) / "blitz-summary.json", report)
    return report


def aggregate(input_dir, output_dir):
    """Merge per-job directories without treating duplicate artifacts as finds."""
    input_dir, output_dir = Path(input_dir).resolve(), Path(output_dir).resolve()
    if input_dir == output_dir:
        raise ValueError("aggregate output must differ from input directory")
    directories = set()
    for name in ("blitz-manifest.json", "gaps.tsv", "FOUND.tsv", "VERIFIED.tsv", "native-status.json"):
        for path in input_dir.rglob(name):
            if output_dir not in path.parents:
                directories.add(path.parent)
    reports = [scan_job(directory) for directory in sorted(directories)]
    merged = {}
    for report in reports:
        manifest = report["manifest"]
        provenance = {"directory": str(Path(report["directory"]).relative_to(input_dir)),
                      "run_id": str(manifest.get("run_id", "")),
                      "shard": str(manifest.get("shard", "")), "arm": manifest.get("arm"),
                      "variant": manifest.get("variant"), "files": report["files"]}
        for row in report["candidates"]:
            k = key(row)
            if k not in merged:
                merged[k] = dict(row, provenance=[], evidence=[], verification_evidence=[])
            target = merged[k]
            target["provenance"].append(provenance)
            target["evidence"].extend(dict(e, artifact=provenance["directory"]) for e in row["evidence"])
            target["verification_evidence"].extend(
                dict(e, artifact=provenance["directory"]) for e in row["verification_evidence"])
            target["reported_found"] |= row["reported_found"]
            target["high_merit_raw"] |= row["high_merit_raw"]
            target["raw_complete"] |= row["raw_complete"]
    for row in merged.values():
        row["verification_status"] = verification_status(row["verification_evidence"])
        if len({merit_value(e["merit"]) for e in row["evidence"]}) > 1:
            row["verification_status"] = "CONFLICT"
    candidates = sort_candidates(merged.values())
    counts = Counter(row["verification_status"] for row in candidates)
    result = {"schema_version": 1, "caveat": CAVEAT, "jobs": len(reports),
              "candidate_counts": {state: counts[state] for state in ("OK", "PENDING", "FAILED", "CONFLICT")},
              "ready_record_candidates": sum(r["verification_status"] == "OK" and r["reported_found"] for r in candidates),
              "unique_candidates": len(candidates), "candidates": candidates,
              "artifact_reports": [{k: v for k, v in r.items() if k not in ("candidates", "native_status")}
                                   for r in reports],
              "error_count": sum(r["error_count"] for r in reports)}
    output_dir.mkdir(parents=True, exist_ok=True)
    write_exports(output_dir, candidates)
    write_json(output_dir / "blitz-aggregate.json", result)
    text = (f"artifacts: {len(reports)}\nunique candidates: {len(candidates)}\n"
            + f"ready record candidates: {result['ready_record_candidates']}\n"
            + "\n".join(f"{s}: {counts[s]}" for s in ("OK", "PENDING", "FAILED", "CONFLICT"))
            + f"\nparse issues: {result['error_count']}\n\n{CAVEAT}\n\n"
            + "".join(f"{r['verification_status']}\t{submission_line(r)}\n" for r in candidates))
    atomic_text(output_dir / "blitz-aggregate.txt", text)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aggregate", nargs=2, metavar=("INPUT_DIR", "OUTPUT_DIR"))
    parser.add_argument("--job", metavar="DIRECTORY")
    args = parser.parse_args()
    if bool(args.aggregate) == bool(args.job):
        parser.error("choose --aggregate INPUT_DIR OUTPUT_DIR or --job DIRECTORY")
    report = aggregate(*args.aggregate) if args.aggregate else write_job_report(args.job)
    print(json.dumps(report.get("candidate_counts", report.get("metrics")), sort_keys=True))


if __name__ == "__main__":
    main()
