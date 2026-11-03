# Ten-minute adaptive-depth prototype

Production cloud campaigns are unaffected. The local ranking-only trial is stopped.

Native Praetor probes use P=1439,d=2310,target25,256 raw multipliers per block.
Full baseline sieves every eligible window through 10^7 and selects top10%.
Adaptive sieves all windows through 10^6, ranks by the same expected-pair
operator, deepens only top30% through 10^7, then selects the same final count.
This isolates adaptive depth rather than changing the ranking rule simultaneously.

Both policies include actual native subprocess CPU/wall and setup costs. Deep
subset survivor arrays, hazard q, and lnN must match the independently generated
full baseline for every shortlisted multiplier. Baseline/adaptive deep execution
order alternates. Raw probe outputs and selections are saved for replay.

The union of final selections is tested for all finite-window prime endpoints.
Shared window timings/outcomes are charged to both selecting policies. This is
a paired replay comparison, not two independently timed full hunting runs. All
adjacent in-window gaps contribute, not just the center-containing gap. Merit20+
finds receive an independent next-prime check and are saved separately.

Summary records measured sieve costs, scoring costs, charged endpoint costs,
selection overlap and baseline qualifying hits retained at thresholds5..40.
Interpret only completed paired stages; deadline-interrupted work is censored,
not failure. Its real runtime consumes the 600-second wall budget even though
unfinished stage costs are excluded from policy comparison estimates. Final
selection outcomes can be partially observed at the deadline. No savings claim
should be made from incomplete unequal selection coverage.

This first implementation rebuilds native setup for every shortlisted window.
It does not yet support a cached, noncontiguous batched deepening interface. The
15-second smoke run found identical final selections in its first complete
round but 1.22 adaptive sieve CPU seconds versus .32 for full, demonstrating
setup overhead rather than a speedup. This is an implementation-level result,
not a disproof of adaptive-depth strategies.
