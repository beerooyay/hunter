# Praetor proof-frontier calculus v0.2

A reproducible experiment in **provably constrained, multi-step mathematical repair**.

## Quick start

```sh
cd research/proof-frontier-calculus-v02
sh run_all.sh
```

Requirements: Python 3.10+ and a C11 compiler (`cc` or gcc). No Python package dependencies. The script generates motif families, compiles two independent bridge verifiers, runs tests, enumerates all bridge pairs for `k=2..7`, counts three-way greedy failures for `k=2,3`, and regenerates tamper-resistant arithmetic receipts. On a laptop the exhaustive k7 enumeration may take longer than the smaller tests.

## Files

- `RESEARCH.md`: statements, proofs, limitations, and reproducible result summary.
- `bridge_lab.py`: reference arithmetic and unused-residue shift-set theorem.
- `independent_bridges.c`: independent full-offset enumerator.
- `difference_bridges.c`: independent missing-residue difference-set enumerator.
- `three_way_full.c`: exhaustive comparison of greedy and jointly optimal two-step joins.
- `certificates.py`: canonical proof receipts and independent arithmetic verifier.
- `test_v02.py`: regression and hostile mutation tests.
- `generate_results.py`: regenerates all tables, sharp-bound certificates, and three-way results.
- `results.json`, `sharp_k7_receipt.json`, `greedy_failure_receipt.json`: frozen reference outputs, verified by code, not trusted by hash alone.
- `lean/`: minimal **unverified** Lean/Mathlib formalization candidate of the core difference identity, pinned to Mathlib/Lean v4.35.0. The entire project was run without Lean installed; **the Lean check is pending CI**.

## Trust ladder

| Claim | Evidence |
|---|---|
| Difference-set criterion | Elementary proof in `RESEARCH.md`, independent executable tests |
| CRT phase-count and multiway path existence | Elementary modular proof in `RESEARCH.md` |
| k7 sharp bound 1,858 across 5,230,369 pairs | Two independent full C histograms identical; finite search, no Lean proof |
| Greedy fails on 35,337 of 148,877 k=3 motif triples | Exhaustive finite C enumeration; explicit Python-verifiable example |
| Mathematical historical novelty | **Not established** |
| Prime existence / prime-gap record | **Not claimed** |
| Lean kernel green | **Not achieved locally** |
| Blockchain consensus | **Not implemented** |

## Scientific framing

This is research code, not a production prime-gap search improvement. The finite bridge results are new to the Praetor registry, not automatically new to mathematics. Classical prime-tuple tooling already supports admissibility repair, and additive-combinatorial differences/CRT are known. The testable software-research hypothesis is that **global, proof-carrying frontier planning** yields better semantic-preserving repairs and reduces independent human review cost compared with greedy proof patching.