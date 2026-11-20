#!/usr/bin/env bash
# Launch on the user's own POSIX machine. No hosted-runner production dispatch.
set -euo pipefail
cd "$(dirname "$0")"
PYTHON=${PYTHON:-python3}
SLOTS=${SLOTS:-10}
HOURS=${HOURS:-5}
"$PYTHON" -c 'import gmpy2'
if [ ! -x ./hunter ]; then ./build.sh; fi
mkdir -p build/portfolio
if [ -f build/portfolio/STOP ]; then
  echo 'STOP exists. Remove build/portfolio/STOP explicitly before relaunching.' >&2
  exit 1
fi
nohup "$PYTHON" -u portfolio.py run --slots "$SLOTS" --hours "$HOURS" \
  --state "$PWD/build/portfolio" >> build/portfolio/supervisor.log 2>&1 < /dev/null &
pid=$!
sleep 2
if ! kill -0 "$pid" 2>/dev/null; then
  tail -40 build/portfolio/supervisor.log >&2
  exit 1
fi
printf 'supervisor started: pid=%s; inspect with %s portfolio.py status\n' "$pid" "$PYTHON"
