# Proof-frontier calculus: open-problem audit (experimental v0.1)

This experiment **does not solve** the Collatz conjecture, binary Goldbach conjecture, or open problems in Lean. Instead, it tests whether a research graph can take a global open goal and generate mathematically truthful, useful scoped subgoals, then route these subgoals to kernel checking while preserving the unproved global obligation.

## Cases

- **Collatz:** the global conjecture is open. For any k>0, n=4k+1 undergoes three steps n -> 3n+1 -> (3n+1)/2 -> (3n+1)/4 = 3k+1 <n. This is an elementary known descent lemma, not a solution. An attempted extension to all odd n is false: n=3 maps 3 -> 10 -> 5 -> 16.
- **Binary Goldbach:** the global conjecture is open. The scoped, finite theorem proves every even integer in [4,30] has two prime summands; the instance 100=3+97 is separately proven. Much larger computational bounds are already known, so this is a *formal pipeline demonstration*, not new number theory.
- **Euler's polynomial:** the universally quantified conjecture n²+n+41 prime is false at n=40: 1681=41². The repair n<40 has independent computational evidence but is **not** asserted as a Lean theorem in this version.

## Status gate

The Python graph intentionally refuses to mark any node `kernel_checked`. Only an external Lean/Mathlib build may establish kernel status; this must be recorded separately in release notes with the commit hash, and never applied to global conjecture nodes. SHA-256 protects file integrity, **not truth or novelty**.

## Reproduce

```sh
python3 frontier_open.py
python3 -m unittest -v test_frontier_open.py
cd lean && lake update && lake exe cache get && lake build
```

Lean 4 and Mathlib v4.35.0 are pinned. Do not claim a Lean result until CI passes.

## Comparison to prior work

- **Google DeepMind Formal Conjectures** has thousands of formalized open-problem statements. Our scope ledger is substantially smaller and not a replacement.
- **MechGeo (2026)** already does machine-checked statement repair and counterexamples in geometry. This experiment does not outperform it.
- **Goedel-Prover-V2** is an advanced theorem prover with published benchmark success rates; our deterministic Python audit is not a comparable ML prover.

Our research question: can explicit *scope preservation*, *human-reviewable failure obligations*, and *globally optimized repair paths* reduce the work needed to convert future candidate conjectures into trustworthy, useful statements? This experiment establishes infrastructure, not an advantage.

## Exact finite-time Collatz residue frontier

`collatz_residue_frontier.py` symbolically propagates all 2^h residue classes through the first h Collatz steps. For n=2^h k+r, each step is affine in k because the coefficient stays even before the final step. Its output provides exact coefficients T^h(n)=A_r k+B_r, a symbolic residue-branch trace, and the smallest nonnegative k (if any) beyond which the h-th iterate is less than n. These are **finite-horizon** facts, not universal convergence.

At h=8, 208/256 residue classes satisfy the eventual h-step descent inequality; 48 do not. At h=10, 512/1024 satisfy it. These ratios need not be monotonic in h. Failure of the h-step test does not imply failure to descend at some earlier or later time. Each class was independently checked numerically for k=0,1,2,3. This calculation is exact Python arithmetic with elementary derivation; **the full residue table is not Lean-certified**.

```
python3 collatz_residue_frontier.py
python3 -m unittest -q test_frontier_open.py
```