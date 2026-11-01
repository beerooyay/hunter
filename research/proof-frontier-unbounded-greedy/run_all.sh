#!/bin/sh
set -eu
cd "$(dirname "$0")"
python3 test_theorem.py
cc -O2 -std=c11 -Wall -Wextra independent.c -o /tmp/pfc_unbounded_greedy_verify
/tmp/pfc_unbounded_greedy_verify
python3 construction.py > /tmp/pfc_unbounded_examples.json
printf 'PASS: full proof-frontier greedy obstruction lab\n'