#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
python3 -m unittest -v test_bridge_rank.py
python3 experiment.py
cc -O3 -std=c11 -Wall -Wextra -o count_patterns count_patterns.c
./count_patterns candidates.tsv 4000000 100003 > range_100k_4m.csv
./count_patterns candidates.tsv 8000000 4000001 > range_4m_8m.csv
./count_patterns candidates.tsv 12000000 8000001 > range_8m_12m.csv
./count_patterns candidates.tsv 30000000 12000001 > range_12m_30m.csv
python3 report.py