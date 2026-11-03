# Lossless record-or-target endpoint pruning, ten-minute test

The previous endpoint baseline tested every survivor in a finite window. For a
fixed minimum gap G, a known prime partitions the window: if a partition's span
is <G, it cannot contain consecutive prime endpoints separated by >=G. Search
near the midpoint for a prime anchor, split, and repeat only on partitions still
wide enough. If no interior prime exists between two known anchors, they are
consecutive and their gap is returned. Outer partitions use the first/last
survivor as conservative bounds. Composite outcomes are memoized within each
window to avoid repeated tests after splitting. This is a standard interval
pruning idea; no mathematical novelty is claimed.

A conservative G preserves every possible local record improvement OR merit25
hit. Let L=floor(log(N + smallest_survivor_offset)), computed with directed-down
160-bit arithmetic. L is a lower bound for log(left prime) in the window. Find
the first positive even g satisfying g > records[g]*L OR g >= 25*L. Unknown
record-table entries have threshold0 and therefore remain eligible. Table values
are exact decimal rationals, compared via integer cross-products. For every even
g<G, neither qualification is possible anywhere in the window. This avoids
using a merit25-only cutoff that could discard lower-merit records.

Losslessness is relative to the frozen table, selected finite windows, and the
same BPSW primality oracle. It does not prove global coverage, record acceptance,
or primality certificates. Both algorithms must return exactly the same pairs
above G in EVERY matched window, a stronger check than equal qualifying counts.
An inequality stops the run and saves a counterexample. All tier counts refer
to these frontier-eligible pairs, not a census of lower-merit gaps.

P=1439,d=2310,depth10^7,target25 and the pair ranking remain fixed. One persistent
Praetor probe supplies each shared frozen batch; both endpoint algorithms are
independently executed in alternating order on the same final selections. Native
screen/setup/ranking costs are charged equally. Anchor-specific table/frontier
costs are charged to anchors. Qualifying candidates receive an independent
next_prime check, charged to both pipelines. It is a comparison to the research
full-window evaluator, NOT a speedup claim over Praetor's production conditional
one-sided stopping policy. The native volume engine is not changed.

Tests exhaust every prime/composite labeling of small windows and several gap
thresholds; 400 seeded random patterns compare exact output and ensure no repeated
oracle calls. Separate tests check rational frontier safety and missing entries.
The 15-second smoke completed6 matched windows: 10390 exhaustive versus1036
anchor PRP calls, with identical eligible pairs (no qualifying finds). These are
preliminary observations, not a rare-gap recall estimate.

The final ten-minute run preserves probe outputs, selected multipliers, all
eligible pairs returned by both methods, independent CPU times, PRP counts,
frozen table hash and source. Interrupted comparisons are censored and excluded
from paired results, although they consume the wall budget. No GitHub jobs are
modified or cancelled by this local experiment.
