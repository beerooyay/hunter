#!/bin/sh
set -eu
cd "$(dirname "$0")"
cc -std=c11 -O3 -Wall -Wextra independent_bridges.c -o independent_bridges
cc -std=c11 -O3 -Wall -Wextra difference_bridges.c -o difference_bridges
cc -std=c11 -O3 -Wall -Wextra three_way_full.c -o three_way_full
python3 -m unittest discover -p 'test_v02.py' -v
python3 generate_results.py