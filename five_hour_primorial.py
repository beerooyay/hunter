"""Five-hour independent small-primorial hunt. Bounded, no submissions, reproducible."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import random
import subprocess
import time
import gmpy2
import moon

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--P', type=int, required=True)
    ap.add_argument('--seconds', type=int, default=18000)
    ap.add_argument('--seed', type=int, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    if args.P not in (337, 353, 1439) or not 1 <= args.seconds <= 18000:
        ap.error('unsupported arm or duration')
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)
    d = 2310
    base = gmpy2.primorial(args.P) // d
    start_time = time.monotonic()
    end = start_time + args.seconds
    threshold = 30
    state = dict(P=args.P, d=d, seconds=args.seconds, seed=args.seed,
                 target=threshold, start_utc=time.time(), status='running',
                 windows=0, scored=0, errors=0, timeout_windows=0,
                 lanes={x:dict(tested=0, completed=0, verified=0, best=0,
                              merit20=0, merit25=0, merit30=0)
                        for x in ('ranked','control')}, best=0.0)
    seen = set()
    next_checkpoint = start_time
    def checkpoint():
        nonlocal next_checkpoint
        state['elapsed_seconds'] = round(time.monotonic()-start_time, 2)
        temp = out/'summary.json.tmp'
        temp.write_text(json.dumps(state, indent=2) + '\n')
        temp.replace(out/'summary.json')
        next_checkpoint=time.monotonic()+25
        print(json.dumps({k:state[k] for k in ('P','status','windows','scored','best','elapsed_seconds')}),flush=True)
    hits=open(out/'verified_merit20.tsv','a',buffering=1)
    env = dict(os.environ, HUNTER_PATTERNS='1')
    try:
        while time.monotonic() < end:
            remaining = end-time.monotonic()
            if remaining < 1:
                break
            start = rng.randrange(100000001,900000000001) | 1
            try:
                proc = subprocess.run(
                    ['./hunter','probe',str(args.P),str(d),'64',str(threshold),
                     str(start),'1000000'],
                    capture_output=True,text=True,env=env,
                    timeout=min(30,max(.2,remaining)))
                if proc.returncode:
                    state['errors']+=1
                    if state['errors']>20: raise RuntimeError(proc.stderr[-500:])
                    continue
                candidates = moon.parse(proc.stdout)
            except subprocess.TimeoutExpired:
                state['timeout_windows']+=1
                if time.monotonic()>=next_checkpoint: checkpoint()
                continue
            state['windows']+=1
            state['scored']+=len(candidates)
            if len(candidates)<2: continue
            ranked = sorted(candidates,key=lambda r:r['rate'],reverse=True)
            chosen=[('ranked',ranked[0]),('control',rng.choice(ranked[1:]))]
            if state['windows']%2==0: chosen.reverse()
            for label,candidate in chosen:
                if time.monotonic()>=end: break
                identity=(candidate['m'],label)
                if identity in seen: continue
                seen.add(identity)
                lane=state['lanes'][label]
                lane['tested']+=1
                center=base*candidate['m']
                offsets={}
                for side,sign in (('left',-1),('right',1)):
                    for k in candidate[side]:
                        if time.monotonic()>=end:break
                        if gmpy2.is_bpsw_prp(center+sign*k):
                            offsets[side]=k
                            break
                if len(offsets)!=2:continue
                lane['completed']+=1
                left=center-offsets['left']
                right=center+offsets['right']
                gap=offsets['left']+offsets['right']
                if time.monotonic()>=end:break
                if gmpy2.next_prime(left)!=right:continue
                lane['verified']+=1
                with gmpy2.context(precision=160):
                    merit=float(gmpy2.mpfr(gap)/gmpy2.log(left))
                lane['best']=max(lane['best'],round(merit,6))
                state['best']=max(state['best'],round(merit,6))
                for t in (20,25,30):
                    if merit>=t:lane[f'merit{t}']+=1
                if merit>=20:
                    expr=f"{candidate['m']}*{args.P}#/{d}-{offsets['left']}"
                    hits.write(f"{gap}\t{merit:.8f}\t{expr}\t{label}\n")
            if time.monotonic()>=next_checkpoint: checkpoint()
        state['status']='completed'
    except Exception as error:
        state['status']='error: '+str(error)[:500]
        raise
    finally:
        checkpoint()
        hits.close()
        (out/'method.json').write_text(json.dumps(dict(
            description='repeated fresh windows; top target-score vs random nonwinner',
            P=args.P, divisor=d, sieve_bound=1000000, candidates_per_window=64,
            verification='BPSW endpoints and GMP next_prime; not primality certificates',
            report_threshold=20, target=30,
            no_automatic_submissions=True),indent=2)+'\n')

if __name__=='__main__':
    main()
