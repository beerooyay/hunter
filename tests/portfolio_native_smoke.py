"""Small end-to-end validation, not a production prime-gap campaign."""
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import moon
import research
import portfolio


def main():
    folder = ROOT / 'build/portfolio-ci'
    folder.mkdir(parents=True, exist_ok=True)
    checks = []
    # Check the native finite-window target probabilities against the Python
    # implementation, using identical survivor patterns and no tail extrapolation.
    for target in (30, 40):
        env = portfolio.clean_env()
        env['HUNTER_PATTERNS'] = '1'
        command = [str(ROOT/'hunter'), 'probe', '337', '210', '32', str(target),
                   '100000001', '1000000']
        run = subprocess.run(command, cwd=ROOT, env=env, capture_output=True,
                             text=True, timeout=45, check=True)
        (folder / f'probe-{target}.tsv').write_text(run.stdout)
        rows = moon.parse(run.stdout)
        if not rows:
            raise AssertionError('probe returned no survivor patterns')
        for row in rows:
            lp = research.logprob(row['q'], math.ceil(target*row['ln']),
                                  row['right'], row['left']) / math.log(10)
            if not (math.isfinite(lp) and abs(lp-row['logp']) < 2e-6):
                raise AssertionError(f'target {target}: native/Python probability mismatch')
        checks.append({'target':target, 'patterns_matched':len(rows)})
        # Exercise each dedicated target wrapper and its durable state on a
        # strictly bounded, one-process smoke run. It is allowed to find nothing.
        lane = folder/f'target-{target}'
        lane.mkdir(exist_ok=True)
        shutil.copy2(ROOT/'hunter', lane/'hunter')
        shutil.copy2(ROOT/'records.txt', lane/'records.txt')
        with (lane/'worker.log').open('w') as log:
            run = subprocess.run([sys.executable, '-u', str(ROOT/'portfolio.py'), '_target',
                '--target', str(target), '--seconds', '30', '--seed', str(target),
                '--lane', str(lane), '--queue', str(folder/'verification')],
                cwd=ROOT, env=portfolio.clean_env(), stdout=log,
                stderr=subprocess.STDOUT, timeout=45, check=True)
        summary = json.loads((lane/'learning/summary.json').read_text())
        if summary['status'].startswith('error:'):
            raise AssertionError(summary['status'])
        if f'target-{target}' not in summary['version']:
            raise AssertionError('wrong target-specific history version')
        checks[-1]['worker_status'] = summary['status']
    portfolio.save(folder/'validation.json', {'checks':checks,
         'note':'two 30-second target smoke tests; no production campaign launched'})
    print(json.dumps(checks, indent=2))


if __name__ == '__main__':
    main()
