"""One persistent CPU worker: target-first research, not promised rare-gap yield."""
import argparse
import bisect
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import random
import signal
import sqlite3
import subprocess
import tempfile
import time
from types import SimpleNamespace
import zlib

import gmpy2
import moon
import shared_learning
from calibration import atomic_json, audit, fit, holdout

ROOT = Path(__file__).resolve().parent
ARMS = [(p, d) for p in (337, 1439, 4001, 6007, 8009) for d in (210, 2310)]
TARGETS = (25, 30, 40, 50)
TIERS = (5, 10, 15, 20, 25, 30, 40, 50)
VERSION = "target-learner-v2-shared"


def logadd(a, b):
    if a == -math.inf:
        return b
    if b == -math.inf:
        return a
    return max(a, b) + math.log1p(math.exp(-abs(a-b)))


def logprob(q, gap, right, left):
    """P(nearest endpoints in window AND sum >= gap), independent Bernoulli q."""
    loss, total = math.log1p(-q), -math.inf
    for i, r in enumerate(right):
        j = bisect.bisect_left(left, gap-r)
        if j < len(left):
            term = math.log(q) + (i+j)*loss + math.log(-math.expm1((len(left)-j)*loss))
            total = logadd(total, term)
    return total


def connect(path):
    db = sqlite3.connect(path)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=FULL")
    db.executescript('''
      CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY, version TEXT, target INTEGER, p INTEGER, d INTEGER,
        start INTEGER, status TEXT, seconds REAL, log_yield REAL, selected_by TEXT);
      CREATE TABLE IF NOT EXISTS trials (
        p INTEGER, d INTEGER, m INTEGER, job INTEGER, lane TEXT, q REAL,
        nr INTEGER, er INTEGER, nl INTEGER, el INTEGER, heldout INTEGER,
        result TEXT NOT NULL, pattern BLOB NOT NULL, PRIMARY KEY(p,d,m));
      CREATE TABLE IF NOT EXISTS finds (
        expression TEXT PRIMARY KEY, gap INTEGER, merit REAL, verified INTEGER,
        local_record INTEGER, result TEXT NOT NULL);
    ''')
    return db


def choose(db, target, rng):
    stats = {arm: [] for arm in ARMS}
    for p, d, seconds, value in db.execute(
        "SELECT p,d,seconds,log_yield FROM jobs WHERE status='complete' AND target=? AND version=?",
        (target, VERSION)):
        if seconds > 0 and value is not None:
            stats[p,d].append(value + math.log(3600/seconds))
    untried = [arm for arm, values in stats.items() if not values]
    if untried:
        evidence=shared_learning.read().get('bands',{})
        weights=[]
        for p,d in untried:
            band=evidence.get(f'{p}:{d}',{})
            weights.append(1+min(3,1000*band.get('tails',{}).get('20',0)/max(1,band.get('tested',0))))
        return rng.choices(untried,weights=weights,k=1)[0], "warmup informed by main-search evidence"
    if rng.random() < .2:
        return rng.choice(ARMS), "explore"
    # Shrink short histories toward pooled performance; perturb to preserve uncertainty.
    prior = sum(sum(v[-40:]) for v in stats.values()) / sum(len(v[-40:]) for v in stats.values())
    def draw(arm):
        values = stats[arm][-40:]
        n = len(values)
        mean = (sum(values) + 3*prior)/(n+3)
        variance = max(1., sum((v-mean)**2 for v in values)/max(1,n-1))
        return rng.gauss(mean, math.sqrt(variance/(n+3)))
    return max(ARMS, key=draw), "modeled yield per elapsed hour"


def hazard(db, arm):
    rows = [(q, nr+nl, er+el, h) for q,nr,er,nl,el,h in db.execute(
        "SELECT q,nr,er,nl,el,heldout FROM trials WHERE p=? AND d=?", arm)]
    return fit(rows)


def summary(db, folder, status, phase="idle"):
    lanes = {}
    for (payload,) in db.execute("SELECT result FROM trials"):
        r = json.loads(payload)
        lane = lanes.setdefault(r["lane"], dict(tested=0, completed=0, best=0,
                         observed={str(t):0 for t in TIERS}, predicted={str(t):0. for t in TIERS}))
        lane["tested"] += 1
        lane["completed"] += r["completed"]
        lane["best"] = max(lane["best"], r.get("merit", 0))
        for t in TIERS:
            lane["observed"][str(t)] += int(r.get("merit", 0) >= t)
            lp = r["log_probabilities"][str(t)]
            lane["predicted"][str(t)] += math.exp(lp) if lp is not None else 0
    arms = {f"{p}#/{d}": hazard(db, (p,d)) for p,d in ARMS}
    recipes = []
    for t,p,d,n,seconds in db.execute("SELECT target,p,d,count(*),sum(seconds) FROM jobs WHERE status='complete' GROUP BY target,p,d"):
        recipes.append(dict(target=t, P=p, d=d, rounds=n, seconds=seconds))
    value = dict(version=VERSION, updated=time.time(), pid=os.getpid(), status=status, phase=phase,
                 lanes=lanes, arms=arms, recipes=recipes,
                 finds=[dict(gap=g,merit=m,expression=e) for g,m,e in db.execute("SELECT gap,merit,expression FROM finds WHERE verified=1 ORDER BY merit DESC")],
                 jobs=db.execute("SELECT count(*) FROM jobs").fetchone()[0],
                 records=db.execute("SELECT count(*) FROM finds WHERE verified=1 AND local_record=1").fetchone()[0],
                 verified_targets={str(t):db.execute("SELECT count(*) FROM finds WHERE verified=1 AND merit>=?", (t,)).fetchone()[0] for t in TARGETS},
                 note="Adaptive model, not a neural network. Merit 30-50 predictions are unvalidated. Controls are random within the same refined windows; not a global random-search benchmark.")
    atomic_json(folder / "summary.json", value)
    return value


def run(args):
    folder = args.state.resolve()
    folder.mkdir(parents=True, exist_ok=True)
    lock = (folder / "worker.lock").open("w")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    db = connect(folder / "research.sqlite3")
    with db:
        db.execute("UPDATE jobs SET status='interrupted' WHERE status='running'")
    os.nice(10)
    deadline = time.monotonic() + args.seconds
    def expired():
        if time.monotonic() >= deadline or (folder / "STOP").exists():
            raise TimeoutError("budget exhausted or STOP requested")
    def stop(signum, frame):
        raise TimeoutError("termination requested")
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    status, phase = "running", "starting"
    last_audit = 0
    try:
        while True:
            expired()
            if time.monotonic()-last_audit > 300:
                audit(ROOT)
                shared_learning.refresh(ROOT)
                last_audit = time.monotonic()
            roundid = db.execute("SELECT coalesce(max(id),0)+1 FROM jobs").fetchone()[0]
            rng = random.Random(f"{VERSION}:{args.seed}:{roundid}")
            target = TARGETS[(roundid-1)%len(TARGETS)]
            arm, reason = choose(db, target, rng)
            start = rng.randrange(100000000, 900000000000) | 1
            with db:
                db.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?,'running',NULL,NULL,?)",
                           (roundid,VERSION,target,*arm,start,reason))
            phase = f"round {roundid}: {arm[0]}#/{arm[1]}, merit {target}, {reason}"
            summary(db, folder, status, phase)
            clock = time.monotonic()
            calibration = hazard(db, arm)
            scale = calibration["research_scale"]
            shared=shared_learning.read(ROOT).get('models',{}).get(f'{arm[0]}:{arm[1]}',{})
            if shared.get('applied'): scale=shared['scale']
            with tempfile.TemporaryDirectory(prefix="probe-", dir=folder) as tmp:
                cfg = SimpleNamespace(merit=target)
                coarse = moon.call(cfg, Path(tmp), deadline, "scout", 1000000, arm, start, args.scout)
                winner = max(coarse, key=lambda r:r["rate"])
                fine = moon.call(cfg, Path(tmp), deadline, "refine", 10000000, arm,
                                 max(1,winner["m"]-32),64)
            # Control is drawn BEFORE selection, at exactly the same sieve depth.
            # Its distribution is uniform conditional on the chosen fine window.
            control = rng.choice(fine)
            for row in fine:
                row["lp"] = logprob(row["q"]*scale, math.ceil(target*row["ln"]), row["right"], row["left"])
                row["rank"] = row["lp"]-math.log(max(1.,row["tests"]))
            aimed = sorted((r for r in fine if r["m"] != control["m"]), key=lambda r:r["rank"], reverse=True)[:args.keep]
            chosen = [(control,"control")] + [(r,"aimed") for r in aimed]
            # Balance which lane pays first if a deadline ends a round.
            rng.shuffle(chosen)
            log_yield = -math.inf
            base = gmpy2.primorial(arm[0])//arm[1]
            known=ROOT/'learning/known-records.txt'
            baseline_text = (known if known.exists() else ROOT/"records.txt").read_text()
            baseline = {int(f[0]):float(f[1]) for line in baseline_text.splitlines() if len(f:=line.split())>=2}
            table_hash = hashlib.sha256(baseline_text.encode()).hexdigest()
            for row,lane in chosen:
                expired()
                if db.execute("SELECT 1 FROM trials WHERE p=? AND d=? AND m=?", (*arm,row["m"])).fetchone():
                    continue
                center = base*row["m"]
                endpoints, counts = {}, {}
                tick = time.monotonic()
                for side,sign in (("right",1),("left",-1)):
                    counts[side] = 0
                    for offset in row[side]:
                        expired()
                        counts[side] += 1
                        if gmpy2.is_bpsw_prp(center + sign*offset):
                            endpoints[side] = offset
                            break
                probabilities = {str(t):logprob(row["q"]*scale, math.ceil(t*row["ln"]),row["right"],row["left"]) for t in TIERS}
                probabilities = {k:v if math.isfinite(v) else None for k,v in probabilities.items()}
                result = dict(P=arm[0],d=arm[1],m=row["m"],target=target,lane=lane,
                     q=row["q"],scale=scale,ln=row["ln"],counts=counts,endpoints=endpoints,
                     completed=len(endpoints)==2, seconds=time.monotonic()-tick,
                     log_probabilities=probabilities, table_sha256=table_hash,
                     verification="not requested")
                found = False
                if result["completed"]:
                    gap = sum(endpoints.values())
                    left,right = center-endpoints["left"],center+endpoints["right"]
                    with gmpy2.context(precision=160):
                        merit = gmpy2.mpfr(gap)/gmpy2.log(left)
                    value = float(merit)
                    result.update(gap=gap,merit=value)
                    # Missing table entries are only candidates, not established world records.
                    record = merit > baseline.get(gap,0)
                    if record or merit >= min(TARGETS):
                        expired()
                        valid = moon.verify(left,right)
                        result.update(verified=valid, local_record=bool(record),
                            verification="BPSW endpoints plus next_prime; not certificates",
                            expression=f"{row['m']}*{arm[0]}#/{arm[1]}-{endpoints['left']}")
                        found = valid
                # Every tested candidate, including failed finite-window searches, is retained.
                with db:
                    db.execute("INSERT INTO trials VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                       *arm,row["m"],roundid,lane,row["q"],counts["right"],int("right" in endpoints),
                       counts["left"],int("left" in endpoints),int(holdout(f"{arm}:{row['m']}")),
                       json.dumps(result,allow_nan=False),zlib.compress(json.dumps(row).encode())))
                    if found:
                        db.execute("INSERT OR IGNORE INTO finds VALUES (?,?,?,?,?,?)", (
                            result["expression"],result["gap"],result["merit"],1,
                            int(result["local_record"]),json.dumps(result)))
                # Reward includes both lanes and all round costs; zero observed hits are NOT successes.
                log_yield = logadd(log_yield,row["lp"])
                summary(db,folder,status,phase)
            elapsed = time.monotonic()-clock
            with db:
                db.execute("UPDATE jobs SET status='complete',seconds=?,log_yield=? WHERE id=?",
                           (elapsed,log_yield if math.isfinite(log_yield) else -1e6,roundid))
            summary(db,folder,status,phase)
            print(f"{phase}; {elapsed:.2f}s, {len(chosen)} candidates",flush=True)
            # Export a convenient verified-candidate list; keep strongest representative per gap.
            lines = []
            for gap,merit,expr in db.execute("SELECT gap,merit,expression FROM finds WHERE verified=1 ORDER BY merit DESC"):
                if not any(g==gap for g,_,_ in lines):
                    lines.append((gap,merit,expr))
            temp = folder/"found.tsv.tmp"
            temp.write_text("".join(f"{g}\t{m:.8f}\t{e}\n" for g,m,e in lines))
            temp.replace(folder/"found.tsv")
    except subprocess.TimeoutExpired:
        status = "budget exhausted; checkpoint saved"
    except TimeoutError as error:
        status = str(error)
    except Exception as error:
        status = f"error: {error}"
        raise
    finally:
        with db:
            db.execute("UPDATE jobs SET status='interrupted' WHERE status='running'")
        summary(db,folder,status,"stopped")
        db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        db.close()
        lock.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds",type=int,default=28800)
    parser.add_argument("--state",type=Path,default=ROOT/"learning")
    parser.add_argument("--seed",type=int,default=3050)
    parser.add_argument("--keep",type=int,default=3)
    parser.add_argument("--scout",type=int,default=256)
    args = parser.parse_args()
    if not (1 <= args.seconds <= 604800 and 1 <= args.keep <= 8 and 32 <= args.scout <= 256):
        parser.error("seconds 1..604800; keep 1..8; scout 32..256")
    run(args)


if __name__ == "__main__":
    main()
