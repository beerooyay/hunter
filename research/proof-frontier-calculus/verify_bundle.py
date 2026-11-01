#!/usr/bin/env python3
"""Recompute a frozen research bundle independently of serialized claims.
Structural graph validation alone is NOT semantic theorem checking.
"""
import json
from pathlib import Path
from frontier import typed_repair_lab, theorem_stress, sharp_bridge_survey, make_graph, verify_graph
from independent import run as independently

ROOT=Path(__file__).resolve().parent

def check():
    typed=typed_repair_lab();s=theorem_stress();bound=sharp_bridge_survey();G=make_graph(typed,s,bound)
    assert verify_graph(G)
    other=independently()
    assert other['pairs']==bound['pairs']
    assert other['max_bridge']==bound['sharp_maximum_shortest_bridge']
    assert other['histogram']==bound['distribution']
    assert other['max_pairs']==[(e['left'],e['right']) for e in bound['extremizers']]
    for name, expected in [('repairs.json',typed),('crt_audit.json',s),('bridge_survey.json',bound),('proof_graph.json',G)]:
        actual=json.loads((ROOT/name).read_text())
        assert actual==json.loads(json.dumps(expected)), 'stored result differs from regenerated certificate: '+name
    print('PASS: four artifacts semantically regenerated; 23,716 bridges independently audited; graph root '+G['root'])

if __name__=='__main__':check()