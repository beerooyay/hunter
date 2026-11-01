#!/bin/sh
set -eu
cd "$(dirname "$0")"
python3 proof_receipt.py
python3 test_receipt.py
python3 chain_audit.py > chain_audit.json
python3 conditional_void.py
cc -O3 -std=c11 -Wall -Wextra -o /tmp/praetor_v04_prime_counter count_patterns.c
/tmp/praetor_v04_prime_counter conditional_candidates.tsv 4000000 100003 > conditional_100k_4m.csv
/tmp/praetor_v04_prime_counter conditional_candidates.tsv 8000000 4000001 > conditional_4m_8m.csv
/tmp/praetor_v04_prime_counter conditional_candidates.tsv 12000000 8000001 > conditional_8m_12m.csv
/tmp/praetor_v04_prime_counter conditional_candidates.tsv 30000000 12000001 > conditional_12m_30m.csv
python3 report_v04.py