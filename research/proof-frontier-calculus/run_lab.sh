#!/bin/sh
set -eu
cd "$(dirname "$0")"
python3 frontier.py
python3 test_frontier.py
python3 extremal.py
python3 symmetry.py
python3 verify_bundle.py
printf '\nGREEN: exact integer and symbolic test suite. Lean is NOT RUN.\n'