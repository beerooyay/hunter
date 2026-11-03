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

Initial native results preserve the tested known156200 gap (merit26.4157), but
show no gain: 121.09s baseline versus123.53s anchors. An ordinary6007#/210 range
preserves its record set but takes61.55s versus72.70s and certifies no early skips.
These selected microbenchmarks are not a population discovery-rate estimate.
No default integration is justified by those measurements.

The tracked formal/AnchorRule/volume-results.json records completed paired
measurements without full starting-prime expressions. Raw traces and exact
frozen inputs remain under build/volume-anchor* for local review.
