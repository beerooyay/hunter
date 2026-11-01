# proof-frontier: full theorem formalization vs external proof-repair smoke test

## the exact mathematical claim being tested
The unbounded-greedy theorem constructs concrete finite admissible prime-offset motifs for arbitrarily large primes `p ≡ 1 (mod 3)`, with sequential bridge overhead `2p` and global optimum `6`.

The Python/C verification and ordinary written proof live in `research/proof-frontier-unbounded-greedy/`. **Their correctness is not automatically inherited by the Lean submodules.**

## formalization ledger

| file | theorem-level scope | does NOT establish |
|---|---|---|
| `lean/Optimality.lean` | generic soundness of complete lower-bound certificates and a p=13 modular optimum | arbitrary large motifs |
| `lean/GreedyParam.lean` | parametric even bridge lower bound given a residue certificate; (2,2) modulo-3 obstruction; arbitrary ratio arithmetic | that the real motifs have the necessary residue signature |
| `lean/CRTRealization.lean` | Mathlib-CRT residue lifts into integers, evenness if Q is divisible by 2; reduction of all-prime admissibility to small-prime checks | the concrete set S(U), its exact residues/cardinality/maximum and all required bridge equivalences |

**The full theorem is NOT Lean proved until the concrete CRT-lifted motifs are defined, all modular properties are derived, and the parametric conclusions are linked into a single theorem for every prime p≥13 with p%3=1.**

## external benchmark
- upstream source: `Karifannaa/BlueprintRepair`, file `data/hf/states_v0.jsonl`, original 142-state BlueprintTrace.
- 7 preselected target statements frozen in `frozen_cases.json`.
- baseline: try `omega, norm_num, ring, simp` independently and require exit code 0.
- planned: *manually written* fixed tactic templates based on error category, one deliberately unimplemented factorization case retained.
- each candidate is compiled in a clean temporary Lean file; theorem statement bytes are unchanged.
- `results.json` is produced by CI and attached as an artifact.

**This is not blind human-free inference, and the original broken blueprint dependency graph is not reproduced.** Published BlueprintRepair compares full state repairs with identical models/budgets; our simple tactic pilot is not directly comparable to its 104/142 typed-repair figure.

## what would count as promotion
1. An axiom- and sorry-free Lean statement claiming the original fully explicit infinite-family theorem, with all definitions connected.
2. Reproduction with a pinned toolchain, independent audit and check of formalization fidelity.
3. An actual frozen state-repair benchmark with matched proof budget and project context, and statistically meaningful coverage/human-review improvements.

## what would count as failure
- A counterexample to the explicit CRT motif construction.
- A Lean theorem that silently presupposes the bridge-property conclusion instead of proving it.
- Score increases obtained by changing the target statements.
- No advantage over cheap standard Lean tactics once task difficulty is controlled.
