# Shared learning and merit bands — November 1, 2026

## Public submissions and search evidence

Reviewed primegap-list-project/prime-gap-list at commit
[140cb8e](https://github.com/primegap-list-project/prime-gap-list/commit/140cb8ed5abf3b281c4bcee8837ee48b60ce3da9).
The commit accepts 53 improvements and 8 new gaps by B.Rouyea. All 61
expressions in new-results-2026-11-01.txt match current credited entries;
110 entries in the current table credit B.Rouyea. Later local discoveries
are not automatically submitted.

| Starting-prime digits | Table entries | Best merit | Entries at merit >=30 |
| --- | ---: | ---: | ---: |
| 1–99 | 3456 | 41.9388 | 984 |
| 100–499 | 12402 | 42.5402 | 4475 |
| 500–999 | 13310 | 42.5192 | 1521 |
| 1000–1999 | 19009 | 37.3645 | 70 |
| 2000–3999 | 28270 | 35.6402 | 18 |
| 4000–9999 | 32040 | 32.3376 | 5 |
| >=10000 | 16899 | 29.9333 | 0 |

These are selected records, not trials. Neither success probabilities nor
records per CPU-hour can be estimated from this table alone. The maximum
42.5402 uses 337#/210 at 146 digits; 42.5192 uses 1439#/2310 at 611 digits.
The lab retains both small families while adding 6007 and 8009. Its random
multipliers do not span every multiplier of the published records.

Local observations favored investigating 8009#/2310: best 26.7089, two
merits >=25 among roughly 2465 tested centers at review time. 6007#/2310
reached 25.0428 and 4001#/2310 reached 25.4392. Ordinary stopping rules
censor these observations, exposures differ, and samples are small. These
facts justify exploration, not a claim of superior tail yield.

## Shared paths and safeguards

* Both searches compare against learning/known-records.txt: the public table
  plus independently rechecked local discoveries from either search. Only OK
  ordinary finds and verified lab finds contribute. This prevents rediscoveries
  from being credited as improvements over an obsolete local baseline.
* Every five minutes between research rounds, shared_learning.py refreshes
  per-family evidence. Lab warmup samples all families, with a bounded weight
  from ordinary >=20 observations. Twenty percent exploration remains after
  warmup. This is a heuristic prior, not an unbiased rate estimate.
* Pooled survivor hazard corrections use training data only. Each domain
  separately needs 500 training successes, 100 held-out successes, and at
  least 2 nats held-out likelihood gain. Corrections are bounded to +/-5%.
  Both directions use the same approved correction; otherwise ordinary CPU
  search uses its baseline and the lab retains its own gated calibration.
* Native CPU rows append raw baseline q in column 21 (zero based), preserving
  previous fields. Future fitting uses raw q, avoiding correction feedback.
  Duplicate centers are excluded across domains. GPU transfer is disabled.
* Shared calibration expires after 15 minutes, with baseline fallback at
  the next job start. Already-running jobs retain their startup model.
  A long research round can cause expiry; this safely suspends transfer.
* Each scheduler retains its own compute and yield estimates. Lab modeled
  target probabilities are not relabeled as observed ordinary record rates.
  The common table communicates verified improvements in both directions.

Repeated holdout looks and neighboring-center dependence mean the gates are
engineering safeguards, not a formal significance test. Neither ordinary
hazard calibration nor public maxima validate merit-30–50 predictions.
No speedup or higher discovery rate is claimed without controlled evidence.

## Operation and validation

Run one research worker using a Python with gmpy2 installed:
`python3 research.py --seconds 28800`. It takes an exclusive lock, persists
completed trials in SQLite, and checks learning/STOP or SIGTERM to stop.
Main and research budgets are separate; 13 ordinary workers plus one
low-priority research worker is the current allocation on this 14-core Mac.
Job duration is an estimate, not a hard wall-time limit. Verification can
add short-lived processes. The phone dashboard displays Mac computation.

Validation covers Bernoulli tail probabilities against exhaustive patterns,
contradictory-domain transfer rejection, minimum-evidence gating, deduplicated
refresh, verified-only comparison-table merging, expiry, native baseline
parity, native bounded/invalid/expired corrections, expanded probe support,
and scheduler persistence over three isolated restarts.

The new recipe version collects fresh cost/yield histories because the shared
comparison table and calibration policy changed. Historical trials, survivor
calibration, discoveries, and old recipe reports remain persisted; old recipe
rewards are not silently mixed into the new version.
