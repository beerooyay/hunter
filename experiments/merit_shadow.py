"""One-hour isolated ranking experiment; native Praetor sieve, Python evaluation.
All policies receive the identical frozen corpus and deep sieve. This first
experiment compares rankings, NOT adaptive sieve savings or the full volume policy.
"""
import argparse,hashlib,itertools,json,math,os,random,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import gmpy2
import moon,research


def pair_score(q,gap,a):
    """Log expected qualifying consecutive pairs, fixed gap threshold, O(K)."""
    if not a:return -math.inf
    loss=math.log1p(-q);total=-math.inf;j=1;n=len(a)
    for i,x in enumerate(a):
        j=max(j,i+1)
        while j<n and a[j]-x<gap:j+=1
        if j==n:break
        term=math.log(q)+(j-i-1)*loss+math.log(-math.expm1((n-j)*loss))
        total=research.logadd(total,term)
    return total


def minimum_count(gap,a):
    j=1;best=len(a)
    for i,x in enumerate(a):
        j=max(j,i+1)
        while j<len(a) and a[j]-x<gap:j+=1
        if j==len(a):break
        best=min(best,j-i-1)
    return best


def save(path,value):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2,allow_nan=False));tmp.replace(path)


def selftest():
    a=[-12,-3,2,9,18]
    for q in (.01,.2,.8):
        for gap in (1,10,20,40):
            expected=0
            for bits in itertools.product((0,1),repeat=len(a)):
                ps=[x for x,b in zip(a,bits) if b]
                count=sum(y-x>=gap for x,y in zip(ps,ps[1:]))
                expected+=count*q**sum(bits)*(1-q)**(len(a)-sum(bits))
            lp=pair_score(q,gap,a);actual=0 if lp==-math.inf else math.exp(lp)
            assert abs(actual-expected)<1e-12,(q,gap,actual,expected)
            pairs=[j-i-1 for i in range(len(a)) for j in range(i+1,len(a)) if a[j]-a[i]>=gap]
            assert minimum_count(gap,a)==min(pairs,default=len(a))
    print('PASS exhaustive Bernoulli patterns and quadratic minimum-count reference',flush=True)


def run(args):
    root=Path(__file__).resolve().parents[1];folder=args.output.resolve();folder.mkdir(parents=True,exist_ok=True)
    if (folder/'manifest.json').exists():raise RuntimeError('choose a fresh output folder; prior experiments are immutable')
    import signal
    def stop(signum,frame):raise TimeoutError('stop requested')
    signal.signal(signal.SIGTERM,stop)
    os.nice(10)
    import shutil
    shutil.copy2(root/'hunter',folder/'hunter')
    shutil.copy2(__file__,folder/'merit_shadow.py')
    for name in ('moon.py','research.py','calibration.py','shared_learning.py'):
        shutil.copy2(root/name,folder/name)
    shutil.copy2(root/'records.txt',folder/'records.txt')
    (folder/'source').mkdir(exist_ok=True)
    for source in (root/'src/hunter.lang',root/'rt/hunter_rt.c'):
        shutil.copy2(source,folder/'source'/source.name)
    manifest=dict(seed=args.seed,seconds=args.seconds,P=1439,d=2310,target=25,depth=10000000,
        raw_multipliers_per_round=256,selection_fraction=.1,
        binary_sha256=hashlib.sha256((folder/'hunter').read_bytes()).hexdigest(),
        started=time.time(),gmp=gmpy2.mp_version(),
        scope='Ranking replay on shared native sieve; not the full ordinary stopping policy or an adaptive-depth benchmark. Pair count and centered probability differ in objective. All selected windows get the same full-window evaluation.',
        split='Fixed algorithms; independent deterministic multiplier blocks. No fitting on outcomes. Wall deadline includes all setup, screening and evaluation. Incomplete windows are censored, never failures.')
    save(folder/'manifest.json',manifest)
    deadline=time.monotonic()+args.seconds;rng=random.Random(args.seed)
    policies=('center','pairs','minimum');totals={p:dict(windows=0,cpu_seconds=0.,gaps={str(t):0 for t in research.TIERS},central_gaps={str(t):0 for t in research.TIERS}) for p in policies}
    events=[];rounds=0;tested=0;best=0;status='running'
    def checkpoint():
        budget=min(v['cpu_seconds'] for v in totals.values())
        matched={p:dict(cpu_seconds=0.,windows=0,gaps={str(t):0 for t in research.TIERS},central_gaps={str(t):0 for t in research.TIERS}) for p in policies}
        for p in policies:
            for event in events:
                if p not in event['selected_by']:continue
                if matched[p]['cpu_seconds']+event['cpu_seconds']>budget:break
                matched[p]['cpu_seconds']+=event['cpu_seconds']
                if 'gaps' in event:
                    matched[p]['windows']+=1
                    for name in ('gaps','central_gaps'):
                        for t,n in event[name].items():matched[p][name][t]+=n
        save(folder/'summary.json',dict(status=status,updated=time.time(),rounds=rounds,unique_windows=tested,best_merit=best,policies=totals,matched_budget_cpu_seconds=budget,matched=matched,scope=manifest['scope'],cost_note='CPU charges include native screening plus Python scoring, endpoint testing and independent large-find checks. Reporting/file IO and binary snapshot costs are bounded by the global wall deadline but excluded from policy CPU charges. Shared evaluation is timed once and replayed for each policy selecting that window; this is not three independent runtime benchmarks. Whole windows only; unmatched residual budget is reported.'))
    checkpoint()
    try:
        while time.monotonic()<deadline:
            rounds+=1;start=rng.randrange(10000000,900000000000)|1
            command=[str(folder/'hunter'),'probe','1439','2310','256','25',str(start),'10000000']
            tick=time.process_time();clock=time.monotonic();usage=os.times()
            result=subprocess.run(command,cwd=folder,env=dict(os.environ,HUNTER_PATTERNS='1'),capture_output=True,text=True,check=True,timeout=max(.01,deadline-time.monotonic()))
            child_cpu=os.times().children_user+os.times().children_system-usage.children_user-usage.children_system
            (folder/f'round-{rounds:04d}-probe.tsv').write_text(result.stdout)
            rows=moon.parse(result.stdout);ranking={p:[] for p in policies}
            for row in rows:
                a=[-v for v in reversed(row['left'])]+row['right'];gap=math.ceil(25*row['ln'])
                ranking['center'].append((research.logprob(row['q'],gap,row['right'],row['left']),row['m']))
                ranking['pairs'].append((pair_score(row['q'],gap,a),row['m']))
                ranking['minimum'].append((-minimum_count(gap,a),row['m']))
            keep=max(1,math.ceil(.1*len(rows)))
            chosen={p:{m for score,m in sorted(ranking[p],reverse=True)[:keep]} for p in policies}
            screen_cpu=child_cpu+time.process_time()-tick
            events.append(dict(cpu_seconds=screen_cpu,selected_by=list(policies)))
            for p in policies:totals[p]['cpu_seconds']+=screen_cpu
            save(folder/f'round-{rounds:04d}-selection.json',dict(start=start,screen_cpu=screen_cpu,screen_wall=time.monotonic()-clock,selected={p:sorted(ms) for p,ms in chosen.items()}))
            union=list(set.union(*chosen.values()));rng.shuffle(union);by_m={r['m']:r for r in rows}
            base=gmpy2.primorial(1439)//2310
            for m in union:
                if time.monotonic()>=deadline:raise TimeoutError
                row=by_m[m];a=[-v for v in reversed(row['left'])]+row['right'];center=base*m;primes=[];tick=time.process_time();clock=time.monotonic()
                for offset in a:
                    if time.monotonic()>=deadline:raise TimeoutError
                    if gmpy2.is_bpsw_prp(center+offset):primes.append(offset)
                cpu=time.process_time()-tick;gaps=[];central=[]
                for lo,hi in zip(primes,primes[1:]):
                    merit=float(gmpy2.mpfr(hi-lo)/gmpy2.log(center+lo));gaps.append(merit)
                    if lo<0<hi:central.append(merit)
                    if merit>=20:
                        # Independently recheck large finds; charge verification work too.
                        valid=moon.verify(center+lo,center+hi)
                        with (folder/'finds.jsonl').open('a') as f:f.write(json.dumps(dict(m=m,lo=lo,hi=hi,gap=hi-lo,merit=merit,verified=valid,expression=f'{m}*1439#/2310{lo:+d}'))+'\n')
                cpu=time.process_time()-tick;tested+=1;best=max([best]+gaps)
                payload=dict(round=rounds,m=m,cpu_seconds=cpu,wall_seconds=time.monotonic()-clock,prp_tests=len(a),primes=primes,best=max(gaps,default=0),selected_by=[p for p in policies if m in chosen[p]],gaps={str(t):sum(g>=t for g in gaps) for t in research.TIERS},central_gaps={str(t):sum(g>=t for g in central) for t in research.TIERS})
                with (folder/'windows.jsonl').open('a') as f:f.write(json.dumps(payload)+'\n')
                events.append(payload)
                for p in payload['selected_by']:
                    totals[p]['windows']+=1;totals[p]['cpu_seconds']+=cpu
                    for name in ('gaps','central_gaps'):
                        for t,n in payload[name].items():totals[p][name][t]+=n
                checkpoint()
            print('completed round',rounds,'windows',tested,'best',best,flush=True)
        status='budget complete'
    except (TimeoutError,subprocess.TimeoutExpired):status='budget complete; unfinished window censored'
    finally:checkpoint()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--test',action='store_true');p.add_argument('--seconds',type=int,default=3600);p.add_argument('--seed',type=int,default=20261102);p.add_argument('--output',type=Path,default=Path('build/merit-shadow-20261102'));a=p.parse_args()
    if a.test:selftest()
    else:
        if not 1<=a.seconds<=3600:p.error('seconds must be 1..3600')
        run(a)
