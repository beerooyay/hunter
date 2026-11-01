# Proof-frontier calculus: unbounded sequential greedy trap (v0.1)

**Main result:** an explicit family of *three admissible prime-offset patterns* where a sequential greedy choice has bridge overhead `2p`, while the globally optimal construction has overhead **exactly 6**, for every prime `p≥13` congruent to 1 modulo 3. Therefore no uniform approximation ratio exists for the specified greedy procedure.

This is a general mathematical theorem supported by a detailed proof in [`THEOREM.md`](THEOREM.md). **Historical novelty has not been established, and the theorem has not yet been formalized in Lean.** The constructed tuples are admissible; we do NOT claim they occur as actual primes.

## Verification

- Standard-library Python constructs literal astronomical-but-finite offset sets and checks admissibility modulo every prime relevant to the cardinality bound.
- Independently written C checks the arithmetic residue gadget without calling the Python construction. 79 parameter primes, all green.
- Adversarial tests verify the sharp optimality lower bound, first greedy decision, all smaller second bridges, and input validation.
- Test examples: `p=13` gives greedy cost 26 vs optimum 6; `p=73` gives 146 vs 6; `p=103` gives 206 vs 6.

## Why this matters

It supplies an **explicit obstruction to local-only repair strategies**. A proof-frontier planner cannot promise any uniform factor over the globally best bridge repair without additional restrictions. This is a much sharper negative guarantee than a finite example of greedy failure.

## Prior art and next test

Prime Pages' k-tuple extender already warns that its greedy extension may not be shortest; other optimization and planning literatures establish unbounded greedy failures in different spaces. The precise theorem above needs a focused literature and expert audit. We should pursue Lean formalization of the modular set-gadget, then compare against non-greedy branch-and-bound / constraint solvers with proof receipts.

**Trust labels**: ordinary mathematical proof supplied; finite independent testing green; Lean status pending; literature novelty unresolved; prime occurrence not claimed; production Praetor unchanged.