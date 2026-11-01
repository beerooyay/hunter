# Human mathematical review packet: proof-frontier open-problem pilot

**Scope:** three mathematical challenges, none claimed to be original. Machine-checkable Lean files are in `lean/OpenProblems.lean`; the Python discovery and status manifest is in `open_problem_frontier.json`. These are independently separate evidence channels.

## Problem A: Collatz conjecture

- **Original intended statement (open):** for every positive integer n, a finite Collatz trajectory reaches 1.
- **Proved scoped target (candidate Lean theorem):** for each k > 0, let n=4k+1. Then T(T(T(n)))=3k+1<n. This is a local descent, NOT universal termination.
- **Complementary obstruction (candidate Lean theorem):** for each k >= 0, let n=4k+3. Then T(T(T(n)))=18k+16>n. A uniform three-step descent proof cannot handle this class.
- **Independent arithmetic:** exact symbolic parity branches, numerical verification over 250 and 10,000 representative k values; affine residue tables generated for h in {3,4,5,6,8,10}, checked at k=0,1,2,3 in every cell.
- **Outstanding:** no argument establishes a return or descent for all members of the 4k+3 class after some variable finite number of steps; no proof of the global conjecture.
- **Semantic fidelity:** no restrictions may be removed or treated as equivalent to the global conjecture.

## Problem B: Binary Goldbach conjecture

- **Original intended statement (open):** every even integer n >=4 is a sum of two primes.
- **Proved scoped target (candidate Lean theorem):** for each even n with 4<=n<=30, an explicitly chosen pair of primes sums to n.
- **Certificates:** 4=2+2, 6=3+3, 8=3+5, 10=3+7, 12=5+7, 14=3+11, 16=3+13, 18=5+13, 20=3+17, 22=3+19, 24=5+19, 26=3+23, 28=5+23, 30=7+23. Separate instance: 100=3+97.
- **Independent arithmetic:** all small primes and equalities checked by trial division in Python.
- **Outstanding:** nothing about all even n>30 follows from these finite examples; known literature computes enormously farther already.
- **Formal failure history:** early `by decide` goal failed to synthesize a decision procedure over the implicitly bounded search; a subtype attempt likewise failed. A tactic with incomplete witness choices was also rejected. The latest Lean source uses a true finite case split with one explicit correct witness per branch.

## Problem C: Euler's quadratic

- **Original false statement:** for every n>=0, n^2+n+41 is prime.
- **Counterexample:** at n=40, the value 1681=41*41 is composite.
- **Nearby repaired statement:** primality for integers 0<=n<40; Python tested this finite restriction but its complete proof is NOT included as a Lean theorem in this release.
- **Outstanding:** a repaired finite statement never justifies the original universal claim; this must be visible in the proof graph.

## Current trust boundaries

- Python graph integrity: `sha256` canonical IDs and references, **not logical proof**.
- Numerical tests: reproduce finite observations, **not universal proof**.
- Lean formal theorems: check the Github Actions job on the exact current commit before marking kernel-certified.
- Prior art: Collatz residue-class arguments and finite Goldbach instances are classical. This is a **workflow test**, not new number theory.
- Novelty, mathematical meaning, and usefulness require a separate human decision even after Lean successfully checks a formal statement.

## Reproduction

```
python3 frontier_open.py
python3 collatz_residue_frontier.py
python3 -m unittest -q test_frontier_open.py
cd lean
lake update
lake exe cache get
lake build
```

No `sorry`, `axiom`, or `native_decide` appears in the Lean pilot source.