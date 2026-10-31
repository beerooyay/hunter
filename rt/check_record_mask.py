import json, os, subprocess, math, statistics
from pathlib import Path
import gmpy2
ROOT=Path(__file__).resolve().parent.parent
DATA=ROOT/"build/mask-validation"
DATA.mkdir(parents=True,exist_ok=True)
BIN=ROOT/'hunter'
def run(args, reference=False, dry=False, gpu=False):
 env=dict(os.environ)
 for key in ('HUNT_MASK_REFERENCE','HUNT_DRY','HUNTER_GPU'):env.pop(key,None)
 if reference:env['HUNT_MASK_REFERENCE']='1'
 if dry:env['HUNT_DRY']='1'
 if gpu:env['HUNTER_GPU']='ref'
 r=subprocess.run([str(BIN),'hunt',*map(str,args)],env=env,capture_output=True,text=True,check=True)
 rows=[l.split('\t') for l in r.stdout.splitlines() if l.startswith(('T\t','S\t'))]
 summary=dict(x.split('=',1) for x in next(l for l in r.stdout.splitlines() if l.startswith('#')).split('\t')[1:])
 return rows,summary
def mathematical(rows):
 return [[v for i,v in enumerate(r) if i not in ({4} if r[0]=='S' else {16,20})] for r in rows]
# A synthetic table deliberately makes thresholds cross within the job.
# Real tables usually have no crossings in a short multiplier range.
lnk=float(gmpy2.log(gmpy2.primorial(211)//210))
synthetic=DATA/'crossing-records.txt'
synthetic.write_text(''.join(f'{g} {g/(lnk+math.log(200)):.8f}\n' for g in range(1,100002)))
checks=[]
for label,args,dry,gpu in [
 ('threshold-crossing',[211,210,101,400,1000,10000,0,8,synthetic],True,False),
 ('completed-gaps',[1009,210,77,150,26000,1000000,0,8,ROOT/'records.txt'],False,False),
 ('wavefront',[1009,210,77,150,26000,1000000,0,8,ROOT/'records.txt'],False,True),
 ('empty-range',[1009,210,77,0,26000,1000000,0,8,ROOT/'records.txt'],True,False)]:
 a,sa=run(args,True,dry,gpu);b,sb=run(args,False,dry,gpu)
 assert mathematical(a)==mathematical(b),label
 n=0
 if not dry:
  K=gmpy2.primorial(args[0])//args[1]
  for r in b:
   if r[5]=='1':
    N=int(r[1])*K
    assert N-gmpy2.prev_prime(N)==int(r[6])
    assert gmpy2.next_prime(N)-N==int(r[7])
    n+=1
 checks.append(dict(case=label,rows=len(b),independent_gaps=n))
 print('PASS',checks[-1],flush=True)
# Interleaved isolated dry runs: identical centers, same record snapshot, lambda=0.
# Zero lambda keeps PRP timing calibration from changing the policy.
args=[4001,210,10000001,500,97852,1000000,0,15,ROOT/'records.txt']
times={True:[],False:[]}; expected=None
for reference in [True,False,False,True,True,False]:
 rows,s=run(args,reference,True)
 if expected is None:expected=mathematical(rows)
 assert mathematical(rows)==expected
 times[reference].append({k:float(s[k]) for k in ('score_s','total_s','cpu_s')})
 print('BENCH','reference' if reference else 'cached',times[reference][-1],flush=True)
result=dict(checks=checks,timings={('reference' if k else 'cached'):v for k,v in times.items()})
result['median_speedup']={k:statistics.median(x[k] for x in times[True])/statistics.median(x[k] for x in times[False]) for k in ('score_s','total_s','cpu_s')}
(DATA/'validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result['median_speedup']),flush=True)
