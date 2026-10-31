# Exact optimizations and the deep-sieve frontier (2026-10-31)

## Implemented and validated

The record decision is `g > floor(rec[g] * lnN / 2^64)` in the engine's fixed-point representation. For nonnegative record merits and monotonically increasing lnN, it can switch only from true to false. Evaluate it at the first and last multiplier of a job. Equal endpoint decisions are invariant; only disagreements need recomputation. This reduces record-mask work from O(MG) to O(G + MC), where G is the number of gap sizes and C the number of endpoint disagreements. Advancing the first potentially improving even gap costs O(G) amortized. This assumes valid nonoverflowing input ranges, as used by the scheduler. It does not change the mathematical score or eliminate PRP tests.

Survivor extraction scans inverted 64-bit sieve words and enumerates set bits with trailing-zero count. Offset zero and padding above SL are excluded. Work becomes O(SL/64 + survivors), rather than visiting every offset individually. A C runtime helper supplies the hardware operation missing from the language surface.

Set HUNT_MASK_REFERENCE=1 to restore BOTH the original record-mask scan and original offset scan for differential experiments. Default uses both optimizations. Timing-dependent nonzero-lambda decisions can differ across executions, even with the original engine, so exact differential comparisons use lambda=0. The probability model itself remains unchanged.

## Exact statement within a specified random-sieve model

Let H be n distinct integer offsets of diameter D. For each additional prime p>D choose one residue class uniformly and independently, and delete surviving offsets in that class. Each p can delete at most one surviving offset. Conditional on r survivors, the count transitions r -> r-1 with probability r/p, otherwise stays r. This is exact for this model; it is not an assertion of independent primality or uniformity over a short, fixed multiplier interval.

For the survivor-count probability generating polynomial F(z), one step is

    F_new(z) = F(z) + (1-z) F'(z)/p.

Consequently E[(N)_k] = (n)_k product_p (1-k/p), for 0 <= k <= n. Proof: each ordered k-tuple survives a step iff the chosen class avoids its k distinct classes. This distribution depends on n and the primes, not the spacing of the n offsets, provided all p>D.

For a pair, the normalized singular-series tail is product_{p>L}(1 - 1/(p-1)^2). For integer L>1 this lies between 1-1/(L-1) and 1, by the product/union bound and comparison with sum_{j>=L} 1/j^2. With L=10^9, candidate-specific pair collisions cannot occur inside the current windows and this tail differs from 1 by less than about 10^-9. This bounds the specified arithmetic factor, not actual conditional prime probabilities.

This recurrence might help forecast the effect of extra sieve work. It does not yet solve the record-aware value-of-information problem: spatial endpoint geometry, operation costs, and the actual multiplier ensemble still matter. Exact count probabilities can also be expensive to propagate. No novelty claim is made for these elementary identities.

## Evidence and limits

The accompanying check_record_mask.py compares exact mathematical output columns under reference and optimized execution. It includes an artificial table forcing thresholds to cross within a job, ordinary CPU gaps independently checked using gmpy2, the CPU reference wavefront, an empty range, and interleaved dry-run benchmarks on a fixed record snapshot. rt/test_survivors.c checks 12,291 bitset cases with canaries and address/undefined-behavior sanitizers.

validation.json and deep-validation.json retain raw timings. The shallow benchmark (P=4001,d=210,M=500,SL=97852,L=10^6) gave median 1.022x scoring and 1.018x total-time speedup. This is a small optimization, not a breakthrough. Deep-sieve results and full live-hunt throughput must be reported separately; dry-run gains are not record-yield gains.

Adaptive sieve-depth selection is a research follow-up, not deployed code. First compare equal-budget shallow/deep policies on held-out multiplier ranges with one frozen record table. Charge all sieving, scoring, and verification costs. No claim about RH, prime independence, an unprecedented algorithm, or a large speedup follows from this change.

Deep-sieve benchmark (same workload, L=10^9): reference scoring 0.86s versus optimized 0.83s; total medians 9.53s versus 9.51s. Total difference is too small to establish an end-to-end speedup. All mathematical dry-run outputs match.
