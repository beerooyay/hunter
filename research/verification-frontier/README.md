# Praetor Research Verification Frontier v0.4

**2026-10-31. This is an experimentally checked research tool, not a cryptographically secure blockchain, new number-theory theorem, or Lean-kernel certified proof.** It builds on the v0.3 research bridge PR and the separate proof-frontier v0.3 toy registry.

## Discovery: automatic forced-composite certificates

Let H be a finite set of distinct nonnegative offsets and b an interior offset not in H. If a prime p has

- `#{h mod p : h in H} = p-1`, and
- `#{h mod p : h in H union {b}} = p`,

then for any base n with each `n+h` prime and **larger than p**, we have `p | (n+b)` and `n+b > p`, so `n+b` is composite.

**Proof:** one of the p residue classes of `n+H` union `{n+b}` must be zero. Since each n+h is prime larger than p, none of those are divisible by p. Therefore n+b is divisible by p; since n+b>p, it is composite. This is a classical prime-tuple/admissibility implication, not a novelty claim.

For H=`(0,2,6,12,14,20)`, all 15 interior missing offsets are forced composite using small primes 2,3,5. Consequently, whenever all 6 specified positions are prime and >5, those six primes are consecutive. Example: 17,19,23,29,31,37.

`proof_receipt.py` exports a content-addressed JSON claim and an auditor-readable Markdown sheet. It separates **modular checking**, **endpoint primality verification**, **Lean kernel status**, **human semantic review**, and **historical originality**. Modifying status to “kernel verified” is explicitly rejected by the local checker.

Four of the 289 automatically selected patterns in the fixed two-gap bridge benchmark are completely forced. On these selections approximately 54.2% of non-designated *even* interior positions are forced by small-prime residue obstructions (other positions mostly eliminated by parity). This is a count from this finite testbed, not a general law about prime constellations.

`test_receipt.py` exercises the 4 patterns, 3,000 random mutations, 5 specific semantic manipulations, and a small-integer independent implication cross-check. Passing tests do **not** constitute a Lean formal proof.

## A second experiment: conditional singular-series void penalty

The baseline bridge scorer uses `log S(H) - bridge/log(X)` with a heuristic independent-void penalty. We evaluated a more local first-order model:

`log S(H) - (1/log X) * sum_{b inside but not in H} S(H union {b}) / S(H)`

This is a **heuristic**, not a probability theorem. The term `S(H+{b})/S(H)` is the conditional Hardy–Littlewood weight of an extra prime at b. Local factors for p up to the global diameter bound B are computed from exact residue counts. Beyond B no residue collision can occur; the remaining universal tail (for fixed tuple size and B) is approximated to 100,000. The uncomputed tail is not asserted to be mathematically zero.

Observed consecutive-prime counts on the fixed 289 motif-pair benchmark, starts 100,003 through 30,000,000:

| policy | total consecutive occurrences |
| --- | ---: |
| shortest bridge | 16,779 |
| maximal singular series alone | 2,982 |
| previous simple void adjustment | 19,727 |
| new conditional correction | **19,759** |

The new correction adds only **+0.16%** relative to the previous heuristic, not a meaningful demonstrated improvement. The independent later interval, 12m..30m, recorded 9,205 versus 9,146 (+0.65%), but earlier slices also include regressions. Motif counts overlap. Do not advertise a speedup or new prime-gap discovery from this experiment. A useful negative/limiting result is that the extra arithmetic model makes comparatively little difference to this benchmark. See `benchmark_summary.json`.

## Security assessment: v0.3 is not a permissionless chain

`chain_audit.py` imports the prior `frontier_v03.py` and produces the IDs of **three future proof epochs directly from the public manifest, without a single proof certificate**. The legitimate proof-bundle verifier still requires evidence, so the attack does not forge a valid bundle. Nevertheless, deterministic public epoch IDs, fixed known claims, and arbitrary reproducible proofs do **not** constitute unpredictable or costly proof of work. The registry still lacks permissionless finality, data availability, fork choice and adversarial consensus. Its useful role is provenance, not currency consensus.

## What would make this scientifically useful?

1. Pin the exact Lean4 and mathlib versions, compile the general forced-composite implication, and require a human to check that the formal statement matches the informal theorem.
2. Generate deterministic, independently verifiable certificates for real 1,700-digit Praetor finds, including endpoint primality certificates, rather than marking probable-prime checks as proof.
3. Export portable research receipts: claim, methods, code/input hashes, hypothesis scope, counterexample searches, external citation, review status, unresolved assumptions, recheck commands, and versioned dependency graph.
4. Allow review and acceptance by existing formal math projects like Prove2Me and Proof Commons; do not compete merely on having a dependency graph.
5. Compare time-to-human-review and formal verification overhead, not just synthetic chain throughput.

## Run

Requires Python 3 and C11 compiler. No external Python packages for the core tests. `run_lab.sh` builds the evaluator and reconstructs four independent data slices. Previous policy counts are available in the sibling `research/bridge-frontier/` directory when run from the GitHub research branch.

```bash
sh run_lab.sh
```

For an easily audited artifact: read `auditable_claim.json` and `HUMAN_REVIEW.md`. To compile a Lean theorem in the future requires an installed, pinned Lean+Mathlib toolchain; **none was run here**.