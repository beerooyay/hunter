"""Bounded target-first experiment. Predictions and verified finds stay separate."""
import argparse
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import random
import signal
import subprocess
import sys
import time

import gmpy2

root = Path(__file__).resolve().parent


def parse(text):
    rows = {}
    for line in text.splitlines():
        fields = line.split("\t")
        if len(fields) == 4 and fields[0].isdigit():
            m = int(fields[0])
            rows[m] = dict(m=m, logp=float(fields[1]), tests=float(fields[2]),
                           rate=float(fields[3]))
        elif len(fields) == 4 and fields[0] == "@":
            m = int(fields[1])
            if m not in rows:
                raise ValueError("pattern without a score")
            rows[m]["right"] = [int(v) for v in fields[2].split(",") if v]
            rows[m]["left"] = [int(v) for v in fields[3].split(",") if v]
        elif len(fields) == 4 and fields[0] == "@meta":
            rows[int(fields[1])].update(q=float(fields[2]), ln=float(fields[3]))
    if "probe complete" not in text:
        raise ValueError("incomplete probe")
    for row in rows.values():
        if "right" not in row or "left" not in row:
            raise ValueError("missing survivor pattern")
        for side in ("right", "left"):
            if row[side] != sorted(set(row[side])) or any(v <= 0 for v in row[side]):
                raise ValueError("invalid survivor ordering")
    return list(rows.values())


def verify(left, right):
    return bool(gmpy2.is_bpsw_prp(left) and gmpy2.is_bpsw_prp(right)
                and gmpy2.next_prime(left) == right)


def call(args, folder, end, label, depth, arm, start, count):
    command = [str(root / "hunter"), "probe", str(arm[0]), str(arm[1]),
               str(count), str(args.merit), str(start), str(depth)]
    env = {k: v for k, v in os.environ.items()
           if k not in ("HUNTER_GPU", "HUNT_DRY", "HUNT_MSK")}
    env["HUNTER_PATTERNS"] = "1"
    path = folder / f"{label}.tsv"
    with path.open("w") as output:
        process = subprocess.Popen(command, cwd=root, env=env, stdout=output,
                                   stderr=subprocess.STDOUT)
        try:
            process.wait(timeout=max(.001, end - time.monotonic()))
        except BaseException:
            process.terminate()
            try:
                process.wait(timeout=.5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            raise
    if process.returncode:
        raise RuntimeError(f"probe exited {process.returncode}: {path}")
    text = path.read_text()
    rows = parse(text)
    with gzip.open(path.with_suffix(".tsv.gz"), "wt") as output:
        output.write(text)
    path.unlink()
    return rows


def worker(args, folder, end):
    rng = random.Random(args.seed)
    snapshot = folder / "records.txt"
    source = snapshot.read_text()
    baseline = {int(f[0]): float(f[1]) for line in source.splitlines()
                if len(f := line.split()) >= 2}
    arms = [(337, 210), (337, 2310), (1439, 210), (1439, 2310)]
    bases = {arm: gmpy2.primorial(arm[0]) // arm[1] for arm in arms}
    state = dict(goal=args.goal, target=args.merit, seed=args.seed, seconds=args.seconds,
                 table=hashlib.sha256(source.encode()).hexdigest(), scouted=0,
                 refined=0, tested=0, calls=0, completed=0, censored=0,
                 records=0, targets=0, best=0, rounds=0, status="running",
                 keep=args.keep, scoutsecs=0, refinesecs=0, testsecs=0, verifysecs=0,
                 note="local table improvements; BPSW/next-prime checks, not certificates")
    seen, gaps, found = set(), set(), {}
    begin = time.monotonic()

    def checkpoint():
        state["elapsed"] = round(time.monotonic() - begin, 3)
        state["records"] = len(found)
        temp = folder / "summary.tmp"
        temp.write_text(json.dumps(state, indent=2) + "\n")
        temp.replace(folder / "summary.json")
        lines = [f"{r['gap']}\t{r['merit']:.8f}\t{r['expression']}\n"
                 for r in sorted(found.values(), key=lambda r: -r["merit"])]
        (folder / "found.tsv").write_text("".join(lines))

    def expired():
        if time.monotonic() >= end or (folder / "STOP").exists():
            raise TimeoutError("deadline or stop request")

    checkpoint()
    try:
        while True:
            expired()
            state["rounds"] += 1
            roundid = state["rounds"]
            arm = arms[(roundid - 1) % len(arms)]
            start = rng.randrange(100000000, 900000000000) | 1
            clock = time.monotonic()
            coarse = call(args, folder, end, f"{roundid}-scout", 1000000, arm, start, 256)
            state["scoutsecs"] += time.monotonic() - clock
            state["scouted"] += len(coarse)
            expired()
            # Aim a deeper, narrower sieve around the strongest coarse candidate.
            winner = max(coarse, key=lambda r: r["rate"])
            focus = max(1, winner["m"] - 32)
            clock = time.monotonic()
            fine = call(args, folder, end, f"{roundid}-refine", 10000000, arm, focus, 64)
            state["refinesecs"] += time.monotonic() - clock
            state["refined"] += len(fine)
            order = sorted(fine, key=lambda r: r["rate"], reverse=True)
            chosen = [{**r, "lane": "aimed"} for r in order[:args.keep]]
            excluded = {r["m"] for r in chosen}
            controls = [r for r in coarse if r["m"] not in excluded]
            if controls:
                chosen.append({**rng.choice(controls), "lane": "control"})
            for row in chosen:
                expired()
                center = bases[arm] * row["m"]
                if center in seen:
                    continue
                seen.add(center)
                endpoints, counts = {}, {}
                clock = time.monotonic()
                for side, sign in (("right", 1), ("left", -1)):
                    counts[side] = 0
                    for offset in row[side]:
                        expired()
                        state["calls"] += 1
                        counts[side] += 1
                        if gmpy2.is_bpsw_prp(center + sign * offset):
                            endpoints[side] = offset
                            break
                seconds = time.monotonic() - clock
                state["testsecs"] += seconds
                state["tested"] += 1
                result = {k: row[k] for k in ("m", "logp", "rate", "tests")}
                result.update(P=arm[0], d=arm[1], lane=row["lane"], counts=counts, seconds=seconds,
                              completed=len(endpoints) == 2)
                if result["completed"]:
                    state["completed"] += 1
                    gap = endpoints["left"] + endpoints["right"]
                    left, right = center - endpoints["left"], center + endpoints["right"]
                    with gmpy2.context(precision=160):
                        merit = gmpy2.mpfr(gap) / gmpy2.log(left)
                    value = float(merit)
                    state["best"] = max(state["best"], value)
                    record = merit > baseline.get(gap, 0)
                    target = merit >= args.merit
                    result.update(gap=gap, merit=value, left=endpoints["left"], right=endpoints["right"],
                                  baseline=baseline.get(gap),
                                  record=False, target=False)
                    if record or target:
                        expired()
                        clock = time.monotonic()
                        valid = verify(left, right)
                        state["verifysecs"] += time.monotonic() - clock
                        result["verified"] = valid
                        if valid:
                            expression = f"{row['m']}*{arm[0]}#/{arm[1]}-{endpoints['left']}"
                            result.update(expression=expression, record=bool(record),
                                          target=bool(target))
                            identity = (int(left), gap)
                            if target and identity not in gaps:
                                state["targets"] += 1
                            gaps.add(identity)
                            if record:
                                found[gap] = result
                                baseline[gap] = value
                else:
                    state["censored"] += 1
                with (folder / "tested.jsonl").open("a") as output:
                    output.write(json.dumps(result) + "\n")
                checkpoint()
            checkpoint()
            if roundid % 20 == 0 or state["records"] or state["targets"]:
                print(f"round {roundid}: {arm}, scout {state['scouted']}, "
                      f"tested {state['tested']}, records {state['records']}, "
                      f"target hits {state['targets']}, best {state['best']:.4f}", flush=True)
            if state["records"] >= args.goal:
                state["status"] = "record goal reached"
                break
    except (TimeoutError, subprocess.TimeoutExpired):
        state["status"] = "budget exhausted or stopped"
    except Exception as error:
        state["status"] = f"error: {error}"
        raise
    finally:
        checkpoint()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=int, default=600)
    parser.add_argument("--merit", type=int, default=50)
    parser.add_argument("--goal", type=int, default=50)
    parser.add_argument("--seed", type=int, default=50)
    parser.add_argument("--keep", type=int, default=4)
    parser.add_argument("--folder", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--end", type=float, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not (1 <= args.seconds <= 600 and 1 <= args.merit <= 100
            and 1 <= args.goal <= 1000 and 1 <= args.keep <= 16):
        parser.error("seconds 1..600, merit 1..100, goal 1..1000, keep 1..16")
    if args.folder:
        worker(args, args.folder, args.end)
        return
    folder = root / "build" / time.strftime("moon-%Y%m%d-%H%M%S")
    folder.mkdir()
    (folder / "records.txt").write_bytes((root / "records.txt").read_bytes())
    end = time.monotonic() + args.seconds
    command = [sys.executable, "-u", str(Path(__file__).resolve()),
               "--seconds", str(args.seconds), "--merit", str(args.merit),
               "--goal", str(args.goal), "--seed", str(args.seed), "--keep", str(args.keep),
               "--folder", str(folder), "--end", str(end)]
    print("results:", folder, flush=True)
    process = subprocess.Popen(["nice", "-n", "10", *command], start_new_session=True)
    try:
        process.wait(timeout=max(.001, end - time.monotonic()))
    except (subprocess.TimeoutExpired, KeyboardInterrupt):
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
    summary = folder / "summary.json"
    if summary.exists():
        data = json.loads(summary.read_text())
        if data["status"] == "running":
            data["status"] = "supervisor stopped worker; counts from last checkpoint"
            summary.write_text(json.dumps(data, indent=2) + "\n")
        print(summary.read_text(), flush=True)
    if process.returncode not in (0, -signal.SIGTERM):
        raise SystemExit(process.returncode or 1)


if __name__ == "__main__":
    main()
