#!/usr/bin/env python3
"""Externally sourced, frozen proof-target smoke test (not an ML benchmark).

The tool NEVER modifies theorem signatures. It tries a fixed direct-tactic
baseline, then fixed strategy templates per predeclared error family. This
is NOT autonomous proof repair and does not reproduce BlueprintTrace's
full-module repair evaluation.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from collections import Counter

HERE=Path(__file__).resolve().parent
LAKE=HERE.parent / "proof-frontier-calculus-v02" / "lean"
BASELINES=["omega","norm_num","ring","simp"]
PLANS={
    "omega": "  omega",
    "norm_num": "  norm_num",
    "induction_sum": """  induction n with
  | zero => simp
  | succ n ih =>
    rw [Finset.sum_range_succ, ih]
    ring""",
}
def lean_check(statement, body):
    with tempfile.NamedTemporaryFile("w",suffix=".lean",dir=LAKE,delete=False) as f:
        f.write("import Mathlib\n\n"+statement+" := by\n"+body+"\n")
        name=f.name
    try:
        r=subprocess.run(["lake","env","lean",name],cwd=LAKE,text=True,
                         capture_output=True,timeout=60)
        return r.returncode==0,(r.stderr+"\n"+r.stdout)[-1200:]
    finally: os.unlink(name)

def main():
    raw=json.loads((HERE/"frozen_cases.json").read_text())
    report=[]
    for case in raw["cases"]:
        statement=case["statement"]
        baseline_attempts=[]
        for tactic in BASELINES:
            valid,diag=lean_check(statement,"  "+tactic)
            baseline_attempts.append((tactic,valid))
            if valid: break
        strategy=case["strategy"]
        if strategy in PLANS:
            planned,planned_log=lean_check(statement,PLANS[strategy])
        else:
            planned,planned_log=False,"no repair template implemented"
        row={
          "id":case["id"],"family":case["family"],
          "statement_sha256":hashlib.sha256(statement.encode()).hexdigest(),
          "baseline":bool(baseline_attempts[-1][1]),
          "baseline_tactics":baseline_attempts,
          "planned":planned,"strategy":strategy,
          "planned_diagnostic":"" if planned else planned_log[:350],
          "target_changed":False,
        }
        report.append(row)
        print(f"{case['id']}: baseline={row['baseline']} "
              f"fixed-template={planned} strategy={strategy}",flush=True)
    summary={
      "n_cases":len(report),
      "baseline_proved":sum(r["baseline"] for r in report),
      "template_proved":sum(r["planned"] for r in report),
      "cases_by_family":dict(Counter(r["family"] for r in report)),
      "note":"Externally sourced but manually selected and coded. NOT a blind ML or SOTA comparison.",
      "cases":report
    }
    (HERE/"results.json").write_text(json.dumps(summary,indent=2)+"\n")
    print(json.dumps({k:v for k,v in summary.items() if k!="cases"},indent=2))
    if not all((r["baseline"] or r["planned"] or r["strategy"]=="unimplemented") for r in report):
        raise SystemExit("unexpected unclosed target")
if __name__=="__main__":
    main()
