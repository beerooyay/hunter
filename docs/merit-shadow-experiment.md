# One-hour merit ranking experiment

The production hunter remains stopped. experiments/merit_shadow.py starts one
bounded process, invoking the isolated native Praetor binary for one sieve at
a time. Default wall limit: 3600 seconds including setup and evaluation.

This is the first ranking experiment, NOT an adaptive-sieve speedup benchmark.
It also does NOT replay the complete volume hunter's record-aware conditional
stopping policy. The center comparator is the research worker's existing
finite-window probability score. All three rules share identical deep-sieve
inputs (P=1439,d=2310,depth=10^7,target merit25,256 raw multipliers per round).
They select equal numbers of windows (top10%); the union is evaluated in seeded
random order. Ranking rules are frozen before outcomes are measured:

- center: probability of the gap surrounding the center meeting the threshold;
- pairs: expected count of consecutive prime pairs above the gap threshold
  anywhere in the finite window, under independent survivor outcomes;
- minimum: minimum number of intervening survivors across eligible endpoint pairs.

The pair sum is computed in O(K) with a monotone pointer and geometric tail.
It uses ceil(25*log(center)), the center-log approximation, rather than a
separate logarithm for every endpoint. Actual outcome merits use log(left prime).
The expected-count score is not a probability of at least one qualifying gap.
For these ~600-digit centers the log approximation is negligible, but the
statistical independence assumption remains a substantive unvalidated model.

Every surviving integer in a selected window receives a BPSW probable-prime
check. Adjacent surviving probable primes establish finite-window gap outcomes;
large finds (merit>=20) receive an independent next-prime check. This is not a
primality certificate. No discoveries are silently inserted into production
FOUND.tsv or the persistent learner. Sidecar finds.jsonl retains expressions.

We record all adjacent finite-window gaps AND the center-containing gap.
Thus broader pair scoring cannot be mistaken for improved center-gap detection.
A policy's charged CPU cost is the shared screening/scoring cost plus measured
endpoint/check costs for windows it selected. Shared windows are timed once and
charged to each selecting policy. Summary also replays prefixes under a common
CPU allowance, using whole windows and reporting actual charged time. These
are matched-cost replays, not independent hardware throughput trials. Metadata
IO and reporting are excluded from policy CPU charges but count against the
one-hour overall wall deadline. Unfinished windows are censored, never failures.
At a deadline, results with incomplete selection coverage must not be compared
as equal-sample raw hit totals.

Outputs include binary hash, copied binary, native source, seed, native probe
outputs, frozen selections, per-window outcomes/costs, independently rechecked
large finds, and an atomic summary. Lower thresholds (5,10,15,20) are diagnostic;
one merit25 hit or no merit40 hits cannot establish extreme-tail performance.

Validation: --test enumerates all 32 Bernoulli outcomes for a five-survivor
window, at three hazard values and four gap thresholds, against the linear
pair score. The minimum-count score is checked against exhaustive endpoint pairs.
A short real native-sieve/endpoints smoke run precedes the one-hour experiment.

Language provenance: native sieve and primorial-window construction are Praetor
with C/GMP runtime support. Experiment orchestration, new ranking operator and
BPSW endpoint evaluation are Python/gmpy2. Production volume records use the
Praetor engine; lab/experimental finds must be described as mixed-pipeline finds.
