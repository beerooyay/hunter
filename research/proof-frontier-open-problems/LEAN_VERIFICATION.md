# lean verification receipt: proof-frontier open-problem pilot

**VERIFIED BUILD**

- GitHub repository: `beerooyay/hunter`
- Branch: `research/proof-frontier-open-problems-v01`
- Checked source commit: `dd6c51dadb4724aa53bef464dcdfd9778f314e45`
- Github Actions run: https://github.com/beerooyay/hunter/actions/runs/41266666801
- Job: `kernel-check` (id `124730776042`)
- Result: **success**
- Lean and Mathlib: pinned to version `v4.35.0`
- Excerpt from job log: `Built OpenProblems` and `Build completed successfully (9050 jobs)`
- Verified on GitHub-hosted Linux runner. Local environment did not have Lean installed.

## What is formally proved (and what is not)

1. `Praetor.OpenProblems.collatz_four_k_one_descends`: exact three-step reduction for n=4k+1 with k>0.
2. `Praetor.OpenProblems.collatz_four_k_three_ascends`: exact three-step ascent for n=4k+3 with k>=0.
3. `Praetor.OpenProblems.goldbach_up_to_30`: every even n with 4<=n<=30 has two explicit prime summands.
4. `Praetor.OpenProblems.goldbach_at_100`: 100=3+97 with primality checked.
5. `Praetor.OpenProblems.euler_polynomial_counterexample`: 40²+40+41 is not prime.
6. `Praetor.bridge_iff_missing_difference`: prior core bridge theorem imported/built in the same Lake project.

The `CollatzConjecture` and `GoldbachConjecture` declarations merely **define** the full open statements. They have **no proofs**. The h=3..10 Collatz residue table has exact Python arithmetic evidence but is not itself Lean-formalized. The original false Euler universal statement is not asserted.

Source file includes no `sorry`, `axiom`, or `native_decide` commands. A successful Lean build establishes validity of the checked restricted formal theorems, not semantic fidelity, publication novelty, or global resolution of the open problems.

## Diagnostic trail

- Run 41266143434 failed: Lean could not synthesize `Decidable (GoldbachUpTo 30)` from an implicitly bounded universal.
- Run 41266333094 failed: using `Fin` still lacked a synthesized decision procedure.
- Run 41266532610 failed: a tactic branch committed to an incomplete candidate witness rather than exploring alternatives.
- Run 41266666801 passed: exhaustive even-number case split, each case paired with its explicit prime witnesses.

This failure history is intentionally retained as research evidence about trustworthy human-reviewable proof compilation.