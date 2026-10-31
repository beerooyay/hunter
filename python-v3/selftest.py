#!/usr/bin/env python3
"""30-second correctness check after building on a new machine: every gap hunt reports must match gmpy2."""
import subprocess, os, gmpy2
HERE = os.path.dirname(os.path.abspath(__file__))
out = subprocess.run([os.path.join(HERE, 'hunt'), '1009', '210', '77', '300', '26000', '1e8', '0', '8',
                      os.path.join(HERE, 'records.txt')], capture_output=True, text=True).stdout.splitlines()
K = gmpy2.primorial(1009) // 210
n = bad = 0
for line in out:
    f = line.split('\t')
    if f[0] == 'T' and f[5] == '1':
        N = int(f[1]) * K; a, b = int(f[6]), int(f[7]); n += 1
        if gmpy2.next_prime(N) - N != b or N - gmpy2.prev_prime(N) != a: bad += 1
print(f'selftest: {n} gaps checked against gmpy2, {bad} mismatches -> {"PASS" if n and not bad else "FAIL"}')
