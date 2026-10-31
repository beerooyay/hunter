# Praetor bridge frontier: exact singular-series ranking + gap-aware construction

**Research-only experiment, 2026-10-31.** This lives apart from the production Praetor hunter and proof-frontier blockchain. It proves exact algebraic ranking identities, then tests a **heuristic** objective for *consecutive* prime patterns. None of the observed gains establish a new global theorem, a prime-gap record, or speedups for 1,700-digit hunting.

## 1. The exact theorem, and what is not proved

Let `H1` and `H2` be admissible, distinct, **equal-cardinality** sets of integer offsets with minima zero, both contained in `[0,B]`. Let `nu_p(H)` count the distinct residues mod prime `p`. The Hardy–Littlewood singular series is

`S(H) = product_p ((p - nu_p(H))/p) / ((p - 1)/p)^k`.

For every `p > B`, all offsets are distinct modulo `p`, so `nu_p(H1)=nu_p(H2)=k`. Thus all those Euler factors cancel in the ratio. Within `p <= B`, all factors independent of `H` cancel too. **Therefore**

`S(H1)/S(H2) = R_B(H1)/R_B(H2)`, where

`R_B(H) = product_{p prime <= B} (p - nu_p(H))`.

This is an **exact rational identity** involving positive integers. No numerical approximation to the infinite series is needed to compare patterns of equal size and bounded diameter. It follows from the classical singular-series formula; mathematical novelty is not claimed. The Hardy–Littlewood *prime count prediction* is still conjectural.

### A useful second proposition: dominance and a tiny decision frontier

For a bridge `g`, define `R(g)>0` as above. Consider heuristic objectives of the form `log R(g) - alpha*g`, with `alpha > 0`. If `g1 < g2` and `R(g1) >= R(g2)`, then `g2` can **never** win under any positive `alpha`. This is elementary but allows an **exact, lossless Pareto prune** before applying an approximate void penalty.

For the 289 two-gap motif pairs, at most 8 bridge candidates survive this prune (median 4), from up to 48 even candidates in `[2,96]`. The bridge optimizer works with that much smaller decision frontier. Ties prefer smaller bridges.

## 2. Real distinction exposed by the experiment

*Simultaneous prime tuple*: all the prescribed offsets are prime. More primes may lie between them.

*Consecutive-prime word*: **all** the prescribed offsets are prime, and **no** extra primes occur anywhere between the first and last offset.

These are different objective functions. A bridge can improve the first and harm the second.

We exhaustively constructed 289 ordered pairs of admissible two-gap words over `{2,4,6,8,10}` (17 possible source motifs), each using one bridge from the even integers `2..96`. Three policies were fixed **before testing against real primes**:

- `shortest`: smallest admissible bridge;
- `max_series`: largest **exact singular series**, using the integer score `R_B`;
- `void_adjusted`: maximize `log R_B - bridge/log(10^7)`. This is a **Poisson-like void heuristic**, not an exact conditional-prime probability. The reference scale `10^7` is predeclared; no fitting to measured prime counts.

## 3. Reproducible prime-occurrence benchmark

Independent C11 code sieves integers to 30 million plus the small maximum offset. Starting primes are sampled exhaustively in the disjoint ranges specified. Each candidate prime tuple is tested exactly using the sieve, and exact consecutive-prime words additionally require the prime count in the enclosing interval to be exactly six.

| starting-prime range | shortest consecutive | series-only consecutive | void-adjusted consecutive | uplift vs shortest |
|:--|--:|--:|--:|--:|
| 100,003–4,000,000 | 4,267 | 573 | 4,971 | +16.5% |
| 4,000,001–8,000,000 | 2,631 | 461 | 3,100 | +17.8% |
| 8,000,001–12,000,000 | 2,202 | 385 | 2,510 | +14.0% |
| 12,000,001–30,000,000 (additional range) | 7,679 | 1,563 | 9,146 | +19.1% |
| **total** | **16,779** | **2,982** | **19,727** | **+17.6%** |

Across all four ranges, **simultaneous** prime tuples were `28,433` / `78,308` / `42,702` for shortest / series-only / void-adjusted respectively. Maximizing the singular series alone yields **2.75x** the baseline simultaneous tuples yet **82% fewer consecutive** patterns. The void-adjusted construction yields **17.6% more consecutive occurrences** than shortest on these fixed candidate families.

**Limitations:** Counts across patterns can overlap, and the 289 motif pairs have related arithmetic structures. Do not treat occurrences as independent Bernoulli trials or quote an IID p-value. These are small-integer computational observations on a predeclared family; they do **not** establish generality, novelty priority, higher prime-merit yield, or an advantage for Praetor's existing primorial-center search. It is not a randomized equal-compute comparison of gap hunters. Larger windows and other motif sizes may behave differently. The longer range was run after the first, and supports the direction without proving universal generalization.

## 4. Why this is useful for Praetor

The current hunter targets **large empty prime intervals**. This experiment shows why learning a new scoring objective matters: maximizing the simultaneous occurrence of selected anchor primes can increase the probability of extra interior primes, undermining consecutiveness. It suggests using the graph's exact modular certificates for **candidate construction**, followed by a merit-aware conditional void model and a real end-to-end benchmark against the current hunter.

The CRT bridge construction from the earlier research remains a guarantee of **admissibility only**, not prime occurrence. The new exact score is an efficient way to rank candidate prime tuples; the adjusted objective is a separately labeled heuristic. A sensible next experiment is to replace the simple `bridge/log N` penalty by a conditional factorial-cumulant / inclusion–exclusion estimate with careful calibration, then test against held-out real prime-gap outcomes.

## 5. Run it

Requires Python 3.11+ and a C11 compiler; no third-party Python libraries or external network.

```sh
cd research/bridge-frontier
python3 -m unittest -v test_bridge_rank.py
python3 experiment.py
cc -O3 -std=c11 -Wall -Wextra count_patterns.c -o count_patterns
./count_patterns candidates.tsv 12000000 100003 > observations.csv
./count_patterns candidates.tsv 30000000 12000001 > range_12m_30m.csv
# or rerun all four disjoint ranges and aggregate:
./run_lab.sh
```

`test_bridge_rank.py` cross-checks the exact singular-series ratio with independently assembled rational Euler factors, verifies Pareto dominance across multiple scales, checks invalid inputs, and independently reproduces a small C prime-counting sample with a separate Python sieve. Benchmark CSV and JSON reports are included for auditability.

### Relevant literature and prior art

- [Kedlaya, *Prime k-tuples*](https://kskedlaya.org/ant/chap-k-tuples.html), definition of the singular series and Hardy–Littlewood's conjecture.
- [MathWorld, *Prime Constellation*](https://mathworld.wolfram.com/PrimeConstellation.html), classical admissible constellations.
- [Wu and Wu, *The k-tuple prime difference champion* (2019)](https://www.sciencedirect.com/science/article/pii/S0022314X18302816), importance of singular-series-optimized tuples.

**Status: proven classical algebraic identity + measured heuristic improvement. Not a novel number-theory theorem, not Lean certified, not integrated into the production miner or blockchain.**