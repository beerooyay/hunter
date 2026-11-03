# Engine audit: merit-40 feasibility and useful work per CPU-hour

Read-only audit while the existing hunt remains active. No search policy was changed.

## Search support

Main families remain P=4001,6007,8009,12007 with d=210,2310. Their
half-windows SL are about 97800,147400,196900,296100. At current multiplier
positions, 2*SL/log(N) is about 49.8–49.93. Thus a merit-40 gap can fit
inside each window; this does not prove one exists in a given scanned range.
Both bounding primes must fall inside the window. Asymmetric gaps can be
missed even when their total gap is less than 2*SL. The main finite-window
configuration effectively cannot report merit 50. Widening the window costs
work and does not itself increase the density of exceptional gaps.

The lab searches P=337,1439,4001,6007,8009 with both denominators. Its
half-window is target*P, not target*log(N), and the two are only approximately
equal. Its probe supports multipliers through 10^12, while random starts are
between 10^8 and 9*10^11. The public 1439#/2310 example at merit 42.5192
uses m=17440361647223, outside this implementation's multiplier cap. This
proves the wider family has produced merit >40; it is not evidence that
moving near that known discovery will yield another.

## Objective and model

Main scheduling learns modeled table improvements per CPU-hour, retaining
recent job rewards, not a merit-40 objective or a direct observed-hit posterior.
The right endpoint is searched first; the left endpoint is searched only when
conditional expected record value justifies its cost. This is useful for volume
but censors the merit distribution. It is not equivalent to checking every
selected center completely for a merit threshold.

The lab uses complete finite-window endpoint testing and a geometric-survivor
model in log space. It tests 3 ranked candidates plus one random control from
the same refined window. That control measures within-window ranking; it does
not establish that scouting selects better windows than random windows at
matched total cost. Coarse scouts cover 256 consecutive multipliers, then refine
64 around the highest modeled rate. Broad independent window coverage and
reuse of the deep sieve are plausible improvements, not measured gains.

At the inspected checkpoint: 17736 finished candidates, total predicted merit-40
hits 1.46284e-6, zero observed. Repeating that same mixture would require roughly
1.21e10 tested candidates per model-expected hit. This is a model diagnostic,
not a reliable waiting-time forecast; the extreme tail is unvalidated and an
adaptive mixture can change. A few-percent hazard fit does not establish tail
accuracy or improve rare-gap ranking on its own. No shared correction passes
both-domain gates at this checkpoint.

## Costs and candidate improvements

Each native probe repeats prime generation, K-mod-p setup, PRP calibration and
bitset allocation. Coarse depth is 10^6, fine depth 10^7, versus the main
hunter's 10^9. Different depths require matching costs and baseline calibration;
a deeper sieve removes composites but its setup must be amortized.

The native engine already caches K mod p and implements a modular search for
large-prime hits across multiplier intervals. These are combined-sieve ideas;
implementing that algorithm name again is not a new optimization.

A concrete measured overhead is lab summary generation: 0.331,0.421,0.444
wall seconds across three read-only replays at this database size. The worker
recomputes full-history summaries before a round, after every tested candidate,
and after the round. Each candidate is already committed transactionally before
its dashboard summary. Incremental aggregation or throttled dashboard refresh
can reduce reporting work without dropping committed observations. This needs
an isolated benchmark with identical output and a clean deployment; the active
worker was left unchanged. Its current full-history work grows with database size.

Priority experiments:
1. Incremental reporting and persistent sieve/setup reuse: measure end-to-end
   candidate throughput, not just a faster scoring kernel.
2. Broader coarse scouting followed by deep sieving only for a shortlist.
   Compare against independent random-window controls at equal total CPU cost.
3. Compare smaller P bands, alternate denominators, and sieve depths using
   expected target yield per full pipeline cost, with observed lower thresholds
   as diagnostics. Retain a fixed exploration budget.
4. Permit high-value asymmetric-window extension, charge its extra testing cost,
   and evaluate separately from ordinary record-volume policy.
5. For GPU work, benchmark existing Metal kernels at the intended integer sizes;
   CUDA results on Nvidia hardware do not transfer automatically to Apple Metal.

Public references:
- https://arxiv.org/html/2012.03771v1
- https://github.com/sethtroisi/prime-gap/blob/main/THEORY.md
- https://primegap-list-project.github.io/faq/

Troisi reports 30–70% end-to-end gains for his implementation and experiments;
this is neither a forecast for Praetor nor evidence of an available 10000x
end-to-end improvement. Larger integers require more expensive primality tests
and larger absolute gaps to reach the same merit. Preserve ordinary throughput
while evaluating a separate target-first policy.
