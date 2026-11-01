# full unbounded-greedy theorem: human-auditable formalization ledger

**Goal:** `FullGreedyGoal.FullUnboundedGreedy` in `lean/FullGreedyGoal.lean`. This is a fully specified Lean **Proposition**, not a proven theorem. The source is frozen as an all-prime, finite-offset, non-vacuous statement.

## Completed independently checked subproofs
- `GreedyParam.even_bridge_residue_lower_bound`: given odd modulus p and exact residue condition, a positive even h cannot be smaller than 2p-2.
- `GreedyParam.only_cheaper_path`, three-residue obstruction, and the elementary unbounded arithmetic ratio lemma.
- `CRTRealization.lift_single_residue`, `lift_finite_residues`: CRT lifts modulo p and Q.
- `CRTRealization.all_primes_of_small_prime_checks`: a bounded-cardinality set only needs finitely many small prime residue checks.
- `Optimality`: general complete-certificate-to-minimum inference.

These are independent formalized implications, **not** a kernel proof of the entire family.

## Submitted for kernel checking
- `CRTSet`: exact finite target residue set realization and cardinality bound.
- `AdmissibleLift`: all-prime admissibility of a CRT-lifted finite motif assuming explicit small-prime divisibility conditions.
- `PrimeParameters`: arbitrarily large prime p ≡ 1 mod 3, using Mathlib's formal arithmetic-progression theorem.

Only mark these as passed after the corresponding successful GitHub workflow run.

## Outstanding real proof obligations
1. Define `Q := ∏ {q : q prime, q≤N, q≠p}` as a finite product and prove `p.Coprime Q`, `2∣Q`, and every other small prime divides Q.
2. Define the **anchored motif** `S(U)` containing 0 and D=pQ, with one representative for each nonzero target residue, and prove all points are even, the maximum is **exactly D**, cardinality is `|U|+1`, and residue image is exactly U.
3. Construct `A,B,C` from complements `{1,7}`, `{-1,3}`, and `{1}`; prove `A.card=p-1`, `B.card=p-1`, `C.card=p`, each is independently admissible.
4. Prove the translated **three-set union** has precisely the residue behavior used in the ordinary proof for q=2,3,p; show all q≥5 other than p occupy at most three classes, and all q>N are harmless.
5. Derive first greedy bridge 2, second greedy bridge 2p-2, alternative globally optimal (4,2) with cost 6, and exclusion of all cheaper even-positive candidates.
6. Use infinitely many primes p≡1 mod3 to establish the arbitrary approximation ratio without assuming that such parameters exist.

At no stage may the conclusion of items 2–5 be included as an unverified hypothesis. `FullUnboundedGreedy` must be closed by Lean without `sorry` or extra axioms. A compiling `def` of the target is NOT its proof.

## Benchmarks
The seven external target-only smoke tests are documented in `../pfc-external-smoke/RESULTS.md`. 5/7 fixed tactics, 6/7 manual templates. They do not reproduce original full broken blueprint states; no autonomy or leaderboard superiority claimed.

## Independent review
A useful expert audit should check that `span` and the actual additive bridge-overhead objective in Lean match the ordinary theorem in `research/proof-frontier-unbounded-greedy/THEOREM.md`; this is precisely where a formalization-fidelity bug could otherwise give us a false green.
