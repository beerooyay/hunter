"""Reproducible, bounded campaign plan and a single shared record snapshot."""
import argparse
import hashlib
import json
import os
import re
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent
COMPILER_SHA = "e51ddcc577bbb2030c75c0b3bbb2ac2ce85c47cd"
MERITS_URL = "https://primegaps.cloudygo.com/merits.txt"


def matrix(shards=100):
    if shards not in (20, 100):
        raise ValueError("choose the 20-shard one-wave or 100-shard full campaign")
    # Each ten-job group has the same mix, so queued waves are comparable.
    # 40/40/20 by family; 80 baseline + 20 half-cutoff, interleaved in advance.
    group = [
        ("6007.2310", "baseline"), ("8009.2310", "baseline"),
        ("6007.210", "baseline"), ("6007.2310", "half-cutoff"),
        ("8009.2310", "half-cutoff"), ("6007.2310", "baseline"),
        ("8009.2310", "baseline"), ("6007.210", "baseline"),
        ("6007.2310", "baseline"), ("8009.2310", "baseline"),
    ]
    return {"include": [dict(shard=i, arm=group[i % 10][0], variant=group[i % 10][1])
                        for i in range(shards)]}


def prepare(source=None, shards=100):
    declared_matrix = matrix(shards)
    if source:
        data = Path(source).read_bytes()
    else:
        request = urllib.request.Request(MERITS_URL, headers={"User-Agent": "Hunter-blitz/1"})
        with urllib.request.urlopen(request, timeout=60) as response:
            data = response.read(20_000_000)
    records = {}
    for line in data.decode("utf-8").splitlines():
        fields = line.split()
        if len(fields) < 2:
            continue
        gap, merit = int(fields[0]), Decimal(fields[1])
        if gap < 1 or not merit.is_finite() or merit <= 0:
            raise ValueError("invalid live record row")
        if gap in records:
            raise ValueError("duplicate gap in live record table")
        records[gap] = (merit, line)
    if len(data) < 1_000_000 or len(records) < 100_000:
        raise ValueError("refusing a missing or truncated record snapshot")
    local = ROOT / "blitz/known-results.tsv"
    updates = []
    for line in local.read_text().splitlines():
        fields = line.split()
        if len(fields) != 3 or not re.fullmatch(r"\d+\*\d+#/\d+-\d+", fields[2]):
            raise ValueError("invalid known local result")
        gap, merit = int(fields[0]), Decimal(fields[1])
        if gap not in records or merit > records[gap][0]:
            records[gap] = (merit, f"{gap} {merit:.4f} B.Rouyea")
            updates.append(line)
    # No shared calibration or hidden prior from an unrelated experiment.
    if (ROOT / "learning/known-records.txt").exists() or (ROOT / "learning/shared-scale.tsv").exists():
        raise RuntimeError("unexpected local learner overlay in clean build")
    snapshot = ("\n".join(records[g][1] for g in sorted(records)) + "\n").encode()
    (ROOT / "records.txt").write_bytes(snapshot)
    manifest = dict(
        schema_version=1, prepared_at=datetime.now(timezone.utc).isoformat(),
        source_url=MERITS_URL, source_sha256=hashlib.sha256(data).hexdigest(),
        records_sha256=hashlib.sha256(snapshot).hexdigest(), record_rows=len(records),
        local_known_sha256=hashlib.sha256(local.read_bytes()).hexdigest(),
        local_known_count=len(local.read_text().splitlines()), local_overlay_updates=updates,
        compiler_sha=COMPILER_SHA, hunter_sha=os.environ.get("GITHUB_SHA"),
        hunter_binary_sha256=hashlib.sha256((ROOT / "hunter").read_bytes()).hexdigest()
        if (ROOT / "hunter").exists() else None,
        matrix=declared_matrix, search_seconds=18000, job_seconds=60,
        objective="record-table improvements; measured tails at merit 20/25/29/30",
        experiment=f"{shards // 5} half-cutoff shards; unproven yield hypothesis",
    )
    (ROOT / "build-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", action="store_true")
    parser.add_argument("--github-output", action="store_true")
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--source")
    parser.add_argument("--shards", type=int, choices=(20, 100), default=100)
    args = parser.parse_args()
    if args.prepare:
        manifest = prepare(args.source, args.shards)
        print(json.dumps({k: manifest[k] for k in ("prepared_at", "record_rows", "records_sha256", "compiler_sha")}))
    if args.matrix:
        value = json.dumps(matrix(args.shards), separators=(",", ":"))
        if args.github_output:
            with open(os.environ["GITHUB_OUTPUT"], "a") as output:
                output.write("matrix=" + value + "\n")
        else:
            print(value)
