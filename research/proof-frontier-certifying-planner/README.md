# proof-frontier calculus: proof-carrying optimal repair v0.1

**Research lab; 2026-10-31.** Builds a shortest-bridge constructor for three admissible prime-offset motifs and issues a complete modular *lower-bound certificate* with a separate verifier. This is a small exact constraint-search experiment, **not** a general autonomous mathematical discovery engine or a solved open prime problem.

## Reproduce

```bash
python3 planner.py
python3 checker.py certificates.json
python3 slack_repair.py
python3 compress.py
python3 test_planner.py
```

No nonstandard Python dependencies. For the formal certificate-soundness module see `lean/Optimality.lean`, built through `research/proof-frontier-calculus-v02/lean` on GitHub with Lean/Mathlib 4.35.0.

## What is proved and what is not

For any three fixed individually admissible even-offset motifs A, B, C, positive even bridges g,h induce a combined offset set. Any obstruction for a prime q ≤ |A|+|B|+|C| is conclusive; no larger prime can obstruct (too few offsets). The planner finds the minimum g+h at or below the greedy baseline. Its receipt contains every lower-cost positive even pair and a prime q whose residues fill every residue class, proving that cheaper pair is invalid. A separate checker **rebuilds the motifs from the claimed input**, verifies prime moduli, greedy choices, feasibility of the proposed optimum, and coverage of all cheaper pairs. Hence the candidate is globally optimal **for bridge-overhead cost in this exact admissibility problem**.

For adversarial CRT construction parameter p≥13, p≡1 mod 3 prime, the earlier general theorem predicts greedy=2p and optimum=6. Six instances p=13,19,31,43,67,103 pass, with **exactly one lower-cost path** (2,2), blocked at mod 3, independent of p. 3 ordinary motif triples also pass. 30 additional word-triplet cross-checks and adversarial mutations are in `test_planner.py`.

**Lean boundary:** `Optimality.lean` formally establishes (a) the general rule that an accepted candidate plus exclusion of all cheaper candidates proves minimum cost, (b) a *specific modular feasibility surrogate* for p=13 with cost 6. It does **not** establish the infinite family in Lean, prove that the finite case's residue model is equivalent to the gigantic prime-offset construction, or prove that any particular constellation occurs among primes. The Python verifier is independent but not itself formally verified. Lean CI run 41268425838 **passed**, checking the generic certificate-to-minimum theorem and the p=13 modular surrogate. See `LEAN_STATUS.md`; the domain-specific infinite construction and Python checker are not formalized.

## Novelty and comparisons

The generic certificate/optimality implication is elementary and **not new**. Constrained global planning, counterexample-guided repair, typed proof-blueprint edits, and Lean-certified CSP solvers all have strong prior art. Our possible differentiated research agenda is **automatically compiling vague or failed mathematical repairs into small, independently checkable *global* optimality certificates, while preserving semantics and prior failures**. That claim requires broader cross-domain evaluation, not just these prime motifs. The unbounded greedy family is a general theorem candidate with a written argument; historical originality has not been established.

## Trust model

Certificate integrity hashes and independent recomputation do not make arbitrary textual statements true. The verifier accepts only two enumerated input encodings, `crt-adversary` and `gap-words`, and a fixed scope string. Certificate JSON has explicit cheaper-pair obstruction witnesses; it contains no ML and makes no permissionless blockchain/security claims.

## Second domain: mathematically exact fudge-factor repair

The same principle applies to a completely different claim form: a finite-range polynomial inequality with an unknown nonnegative additive slack. `slack_repair.py` finds the least slack, supplies an upper-bound check over the finite domain and a tight witness showing every smaller slack fails. Example: the false claim `n² ≤ 7n` for `0≤n≤20` is repaired to `n² ≤ 7n + 260`; its tight witness is `n=20`. Another example gives `n³ ≤ 4n² + 2475` on `0≤n≤15`. Independent verification accepts all three and rejects corrupted optimum, witness, or scope. This is an **elementary, bounded, explicitly represented claim domain**. It does not parse unrestricted English, prove unbounded inequalities, or advance an open mathematical conjecture.

## Modular nogood certificate compression

`compress.py` converts the explicit all-cheaper-pairs list into residue-pattern exclusions. Each `(prime q, g mod q, h mod q)` is verified to *force a modular obstruction for all bridges with those residues*, and the verifier checks that the union of certified classes covers **every** lower-cost even bridge pair. This reduces 66 individually recorded exclusions to **14 modular nogoods** for the example with optimum 26, and 55 to 11 in another example. It compresses the certificate, not the current verifier's O(number of cheaper alternatives) coverage check. The set-cover heuristic isn't claimed to find the smallest possible certificate. No novelty claim: proof-carrying constraints and unsatisfiability certificates have strong prior art.