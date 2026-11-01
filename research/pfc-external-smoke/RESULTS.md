# frozen external Lean-target smoke test: first results

Reference run: https://github.com/beerooyay/hunter/actions/runs/41269439003 (success)

Upstream data: Karifannaa/BlueprintRepair `data/hf/states_v0.jsonl` (BlueprintTrace, 142 states).
Selection: manually chosen seven target statements (frozen in `frozen_cases.json`). These cases are **external to our code but NOT a blind held-out ML evaluation**. We inspected descriptions and supplied the proof templates manually. The original BlueprintRepair dependency-graph state is **not** tested here; only its target theorem statement.

Each attempt: run the pinned Mathlib/Lean compiler on the exact target signature plus a tactic program. The baseline independently tries `omega`, `norm_num`, `ring`, `simp`; the template condition uses a manually selected proof skeleton. Results:

| source ID | failure class | fixed tactics | typed template | comment |
|---|---|---|---|---|
| p68_bad | redundant_dependency | pass | pass | omega already enough for target |
| p60_bad | missing_dependency | pass | pass | norm_num enough |
| p74_bad | redundant_dependency | pass | pass | omega already enough |
| p103_bad | monolithic_needs_split | fail | pass | prewritten induction skeleton succeeds |
| p88_bad | missing_hypothesis | pass | pass | omega enough for target |
| p27_bad | missing_hypothesis | pass | pass | omega enough for target |
| p117_bad | monolithic_needs_split | fail | fail | no factorization template implemented |

**Totals:** baseline 5/7 (71.4%); hand-authored template 6/7 (85.7%). The only extra success comes from injecting a standard induction. This is not evidence for novel or superior automated proving.

**Published comparison:** BlueprintRepair uses a **142-state full-state harness** with matched model budgets, and reports typed repair 104/142 and source patch 109/142 in one 2026 setup. Our smoke test is not comparable in difficulty, score semantics, costs, or repair autonomy.

**Honest negative result:** for five of seven tasks, generic built-in Lean tactics already suffice to prove the target, leaving no room for our templates to improve proof coverage. The difficult factored-product task remained unsolved. The next justified test is original frozen proof-graph states under matched budgets, not more hand-picked target signatures.

The runner writes `results.json` to the workflow artifacts. To reproduce, run the relevant CI job on the pinned branch.
