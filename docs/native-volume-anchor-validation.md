# Anchor-rule formalization and native volume validation

The Lean project is formal/AnchorRule (Lean4.35.0, standard library only). Its
coverage theorem proves that valid prime anchors plus strict short-cell pruning
preserve every qualifying consecutive pair. The center specialization proves
that two prime witnesses bracketing the center bound the center's surrounding
gap. Kernel builds report only standard propext and Quot.sound, no sorryAx or
custom axioms. It is not a full verified implementation or a proof that a PRP
oracle always identifies primes; see the proof README for the exact boundary.

The prior 12.66x endpoint speedup was versus the exhaustive experimental
all-gap window evaluator. Neither the production volume engine nor the original
center-only high-merit worker used that exhaustive algorithm. It is therefore
not evidence of a 12.66x improvement to either deployed hunter.

The native CPU volume engine now contains an opt-in experimental center
certificate, HUNT_RECORD_ANCHORS=1. It requires HUNT_FIXED_PRP_NS and exits with
code2 otherwise. Normal runs remain unchanged. After the real volume policy
selects a center, the experiment seeks PRP witnesses on both sides with total
span less than G0 (the engine's first table-improving gap). A valid witness
rejects that center as a record source. Otherwise the original nearest-endpoint
scan resumes, reusing every witness/composite test already performed. Record
candidates still receive the original higher-repetition GMP checks. GPU execution
is excluded from this experiment.

X rows expose center, cutoff and both witness distances for independent rechecks.
The experimental path does not preserve a complete calibration sample; it must
not feed a deployed lifetime learner without a distinct censoring/observation
contract. The fixed-cost requirement prevents treating it as a production-ready
adaptive scheduler change. It is deliberately NOT enabled by the server.

Benchmark: experiments/volume_anchor_benchmark.py runs actual `hunter hunt`
subprocesses at production SL and depth10^9, against one frozen record table.
Both modes use the same lambda and frozen per-PRP policy price to remove timing
feedback differences from the record comparison. Actual CPU time includes setup,
sieving, scoring, endpoint work and record checks. Native-model value, calibration
and completed-gap counts are not required to match for certified nonrecords.
Only record preservation is the claimed objective. Ordinary and known-record
inputs are distinguished; positive controls against the frozen older table are
not claimed as new discoveries. Cases finish in alternating baseline/anchor order.
Unpaired timeout work is excluded from speedup ratios.

Default-off parity against the pre-anchor binary passed on a completed-gap
fixture, ignoring timing-only output columns. Oracle tests, persistent-probe
parity tests and existing learner/fleet tests also pass. A guard check confirms
the experimental prefilter cannot be enabled without an explicit frozen price.

Completed native comparisons:

| Case | Baseline CPU seconds | Anchor CPU seconds | Record sets equal | Early skips |
| --- | ---: | ---: | --- | ---: |
| Known6007, unfiltered | 121.09 | 123.53 | yes (one historical record) | 0 |
| Known6007, priced policy | 125.96 | 126.38 | yes (same historical record) | 0 |
| Ordinary6007 | 61.55 | 72.70 | yes (empty) | 0 |
| Ordinary8009 | 40.74 | 48.21 | yes (empty) | 0 |

The two ordinary cases cost 102.29 CPU seconds without the prefilter and
120.91 with it, an 18.2% increase. These are small selected comparisons, not a
population discovery-rate estimate. The main suite reached its bounded budget;
an unpaired case is excluded. The ordinary-only suite completed both pairs.
No early-skip path was exercised in these native cases. Oracle tests exercise
the pruning rule separately; matching native records here is limited evidence.
The production activation gate failed: the experimental prefilter remains OFF.

The tracked formal/AnchorRule/volume-results.json records completed paired
measurements without full starting-prime expressions. Raw traces and exact
frozen inputs remain under build/volume-anchor* for local review.
