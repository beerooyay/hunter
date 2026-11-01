#!/bin/sh
set -eu
cd "$(dirname "$0")"
python3 planner.py
python3 checker.py certificates.json
python3 slack_repair.py
python3 compress.py
python3 test_planner.py