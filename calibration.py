"""Audit survivor hazards with censored trials included; never rewrites hunter state."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import time


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temp.replace(path)


def holdout(key):
    return int.from_bytes(hashlib.sha256(key.encode()).digest()[:4], "big") % 5 == 0


def fit(rows):
    """Rows are (base q, trials, successes, heldout). Censored failures contribute.

    Fit c*q using a weak log-scale prior. Corrections are bounded and must improve
    heldout likelihood. This gate is monitoring, not a significance test: repeated
    looks and dependence between nearby centers preclude that interpretation.
    """
    train = [r for r in rows if not r[3]]
    test = [r for r in rows if r[3]]
    events = sum(r[2] for r in train)
    held_events = sum(r[2] for r in test)
    def score(c):
        return (events + 25) / c - 25 - sum((n - e) * q / (1 - c*q)
                                                          for q, n, e, _ in train)
    lo, hi = .8, 1.2
    for _ in range(40):
        mid = (lo + hi) / 2
        if score(mid) > 0:
            lo = mid
        else:
            hi = mid
    scale = min(1.05, max(.95, (lo + hi) / 2))
    gain = sum(e * math.log(scale) + (n-e) * (math.log1p(-scale*q)-math.log1p(-q))
               for q, n, e, _ in test)
    ready = events >= 500 and held_events >= 100 and gain >= 2
    predicted = sum(q*n for q, n, e, h in rows)
    observed = sum(e for q, n, e, h in rows)
    return dict(rows=len(rows), trials=sum(r[1] for r in rows), successes=observed,
                expected_successes=predicted,
                observed_over_expected=observed/predicted if predicted else None,
                fitted_scale=scale, research_scale=scale if ready else 1.0,
                train_successes=events, holdout_successes=held_events,
                holdout_gain_nats=gain, gate_passed=ready)


def audit(root):
    groups, seen = {}, set()
    invalid = duplicates = 0
    path = Path(root) / "gaps.tsv"
    if path.exists():
        with path.open() as stream:
            for line in stream:
                try:
                    f = line.rstrip("\n").split("\t")
                    key = f[0] + ":" + f[1]
                    q, n, e = float(f[18]), int(f[11]), int(int(f[7]) > 0)
                    if not (0 < q < .5 and n >= e and n > 0):
                        raise ValueError("invalid trial")
                    if key in seen:
                        duplicates += 1
                        continue
                    seen.add(key)
                    groups.setdefault(f[0], []).append((q, n, e, holdout(key)))
                except (ValueError, IndexError):
                    invalid += 1
    result = dict(updated=time.time(), mode="audit only; ordinary hunter q unchanged",
                  note="Right-side trials, including failed searches. Aggregate agreement does not validate merit 30-50 tails. Repeated holdout checks are descriptive.",
                  invalid_rows=invalid, duplicates=duplicates,
                  arms={k: fit(v) for k, v in groups.items()})
    atomic_json(Path(root) / "learning/calibration.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    print(json.dumps(audit(args.root), indent=2))
