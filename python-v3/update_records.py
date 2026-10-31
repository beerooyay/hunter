#!/usr/bin/env python3
"""refresh records.txt (best known merit for every gap size) from the live prime gap list.
run before each night's hunt so the hunter never chases a record someone already broke."""
import urllib.request, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES = ['https://primegaps.cloudygo.com/merits.txt',
           'https://raw.githubusercontent.com/primegap-list-project/prime-gap-list/master/allgaps.sql']

def parse_merits(text):
    out = {}
    for line in text.splitlines():
        f = line.split()
        if len(f) >= 2:
            try: out[int(f[0])] = float(f[1])
            except ValueError: pass
    return out

def parse_sql(text):
    out = {}
    for line in text.splitlines():
        if line.startswith('INSERT INTO gaps VALUES('):
            f = line[len('INSERT INTO gaps VALUES('):].split(',')
            g, m = int(f[0]), float(f[7])
            out[g] = max(m, out.get(g, 0))
    return out

for url in SOURCES:
    try:
        text = urllib.request.urlopen(url, timeout=60).read().decode()
        rec = parse_merits(text) if url.endswith('.txt') else parse_sql(text)
        if len(rec) > 100000:
            with open(os.path.join(HERE, 'records.txt'), 'w') as f:
                for g in sorted(rec): f.write(f'{g} {rec[g]:.4f}\n')
            print(f'records.txt updated from {url}: {len(rec)} gap sizes')
            sys.exit(0)
    except Exception as e:
        print(f'{url}: {e}')
print('could not refresh; keeping the existing records.txt')
