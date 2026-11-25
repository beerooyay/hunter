"""Shared-start admission and exact coverage check for the opt-in 20-shard benchmark."""
import argparse
from collections import Counter
from datetime import datetime
import json
import os
from pathlib import Path
import time

from blitz_plan import matrix

MAX_START_SKEW_SECONDS = 15
MAX_NATIVE_START_SKEW_SECONDS = 30


def start(starts_at, *, clock=time.time, sleep=time.sleep):
    """Do not start a late second wave. Called immediately before the native wrapper."""
    if starts_at <= 0:
        raise ValueError("missing or invalid shared UTC kickoff")
    now = clock()
    if now < starts_at:
        sleep(starts_at - now)
        now = clock()
    admitted = starts_at <= now <= starts_at + MAX_START_SKEW_SECONDS
    return {"planned_epoch_utc": starts_at, "checked_epoch_utc": now,
            "admitted": admitted, "max_skew_seconds": MAX_START_SKEW_SECONDS}


def coverage(reports, run_id, starts_at):
    expected = {(str(r["shard"]), r["arm"], r["variant"]) for r in matrix(20)["include"]}
    seen = Counter()
    terminal = set()
    actual_starts = {}
    foreign_or_malformed = 0
    for report in reports:
        m = report.get("manifest", {})
        identity = (m.get("shard"), m.get("arm"), m.get("variant"))
        if str(m.get("run_id")) != run_id or identity not in expected:
            foreign_or_malformed += 1
            continue
        seen[identity] += 1
        timestamp = m.get("hunt_started_at")
        if isinstance(timestamp, str):
            try:
                measured = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                if measured.tzinfo is not None:
                    actual_starts[identity] = measured.timestamp()
            except ValueError:
                pass
        if (m.get("outcome") == "completed"
                and m.get("stop_reason") == "configured hunt deadline"
                and m.get("hunt_seconds_requested") == 18_000):
            terminal.add(identity)
    on_time = {r for r, t in actual_starts.items()
               if starts_at <= t <= starts_at + MAX_NATIVE_START_SKEW_SECONDS}
    return {
        "expected": len(expected),
        "valid_manifests": len(seen),
        "full_duration": len(terminal),
        "missing_shards": sorted(int(r[0]) for r in expected - set(seen)),
        "not_full_duration_shards": sorted(int(r[0]) for r in set(seen) - terminal),
        "duplicate_shards": sorted(int(r[0]) for r, count in seen.items() if count > 1),
        "foreign_or_malformed": foreign_or_malformed,
        "planned_epoch_utc": starts_at,
        "native_start_skew_limit_seconds": MAX_NATIVE_START_SKEW_SECONDS,
        "first_start_epoch_utc": min(actual_starts.values(), default=None),
        "last_start_epoch_utc": max(actual_starts.values(), default=None),
        "late_or_missing_native_start_shards": sorted(int(r[0]) for r in set(seen) - on_time),
        "complete": (len(terminal & on_time) == len(expected) and not foreign_or_malformed
                     and all(count == 1 for count in seen.values())),
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=("start", "coverage"))
    p.add_argument("aggregate", type=Path, nargs="?")
    a = p.parse_args()
    if a.mode == "start":
        result = start(int(os.environ["HUNTER_STARTS_AT"]))
        Path("one-wave-start.json").write_text(json.dumps(result) + "\n")
        print(json.dumps(result), flush=True)
        return 0 if result["admitted"] else 2
    report = json.loads((a.aggregate / "blitz-aggregate.json").read_text())
    result = coverage(report["artifact_reports"], os.environ["GITHUB_RUN_ID"], int(os.environ["HUNTER_STARTS_AT"]))
    (a.aggregate / "one-wave-coverage.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result), flush=True)
    return 0 if result["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
