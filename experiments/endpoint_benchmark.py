"""Matched-window, independently timed exhaustive versus lossless anchor testing."""
import argparse,hashlib,json,math,os,random,shutil,signal,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import gmpy2,moon
from endpoint_anchors import RecordFrontier,anchor_pairs,all_pairs
from persistent_probe import ProbeWorker
from merit_shadow import pair_score,save
TIERS=(10,15,20,25,30,40)
def run(seconds,out):
 root=Path(__file__).resolve().parents[1];out=out.resolve();out.mkdir(parents=True,exist_ok=True)
 if (out/'manifest.json').exists():raise RuntimeError('fresh output required')
 started=time.time();deadline=time.monotonic()+seconds;os.nice(10)
 table=root/'learning/known-records.txt'
 if not table.exists():table=root/'records.txt'
 shutil.copy2(root/'hunter',out/'hunter');shutil.copy2(table,out/'records.txt')
 for name in ('endpoint_benchmark.py','endpoint_anchors.py','persistent_probe.py','merit_shadow.py'):
  shutil.copy2(Path(__file__).with_name(name),out/name)
 text=(out/'records.txt').read_text();tick=time.process_time();frontier=RecordFrontier(text,2*25*1439,25);frontier_setup=time.process_time()-tick
 save(out/'manifest.json',dict(started=started,seconds=seconds,seed=20261104,P=1439,d=2310,target=25,depth=10000000,tier_count_scope='Only pairs above the conservative record-or-target frontier; not a census of all lower-merit gaps',binary_sha256=hashlib.sha256((out/'hunter').read_bytes()).hexdigest(),table_sha256=hashlib.sha256(text.encode()).hexdigest(),scope='Same selected finite windows, same frozen table, same BPSW oracle. Exhaustive and anchor endpoint costs independently timed in alternating order. Anchors must return every consecutive in-window pair above a conservative exact record-or-target gap frontier. No guarantee beyond the finite windows or about PRP certificates. Production workers unaffected.'))
 totals={p:dict(endpoint_cpu=frontier_setup if p=='anchors' else 0.,prp_tests=0,record_candidates=0,gaps={str(t):0 for t in TIERS}) for p in ('exhaustive','anchors')}
 common=dict(setup_cpu=0.,sieve_cpu=0.,score_cpu=0.,verification_cpu=0.);status='running';windows=0;rounds=0;best=0;worker=None;differences=0
 def checkpoint():
  shared=sum(common.values());full=shared+totals['exhaustive']['endpoint_cpu'];fast=shared+totals['anchors']['endpoint_cpu']
  save(out/'summary.json',dict(status=status,updated=time.time(),rounds=rounds,windows=windows,best_qualifying_merit=best,mismatches=differences,policies=totals,common=common,endpoint_cpu_speedup=totals['exhaustive']['endpoint_cpu']/totals['anchors']['endpoint_cpu'] if totals['anchors']['endpoint_cpu'] else None,estimated_selected_window_pipeline_speedup=full/fast if fast else None,note='Only windows completed by both methods contribute. Interrupted work is censored; it still consumes the wall deadline. Pipeline includes the shared native screen and ranking per policy, not discovery-rate improvement over the production volume stopping policy.'))
 def stop(signum,frame):raise TimeoutError
 signal.signal(signal.SIGTERM,stop);checkpoint();rng=random.Random(20261104);base=gmpy2.primorial(1439)//2310
 try:
  worker=ProbeWorker(out/'hunter',out,deadline);common['setup_cpu']=worker.setup_cpu
  while time.monotonic()<deadline:
   rounds+=1;start=rng.randrange(10000000,900000000000)|1
   rows,cpu,wall,raw=worker.probe(start,256,10000000);common['sieve_cpu']+=cpu;(out/f'{rounds:04d}-probe.tsv').write_text(raw)
   tick=time.process_time();chosen=sorted(rows,key=lambda r:(pair_score(r['q'],math.ceil(25*r['ln']),[-x for x in reversed(r['left'])]+r['right']),r['m']),reverse=True)[:max(1,math.ceil(.1*len(rows)))];common['score_cpu']+=time.process_time()-tick
   save(out/f'{rounds:04d}-selection.json',dict(start=start,selected=[r['m'] for r in chosen]))
   for row in chosen:
    a=[-x for x in reversed(row['left'])]+row['right'];center=base*row['m'];tick=time.process_time()
    with gmpy2.context(precision=160,round=gmpy2.RoundDown):lower=int(gmpy2.log(center+a[0]))
    threshold=frontier.minimum(lower);frontier_cpu=time.process_time()-tick;results={}
    methods=[('exhaustive',all_pairs),('anchors',anchor_pairs)]
    if windows%2:methods.reverse()
    for name,method in methods:
     count=[0];tick=time.process_time()
     def prime(x):
      if time.monotonic()>=deadline:raise TimeoutError
      count[0]+=1;return bool(gmpy2.is_bpsw_prp(center+x))
     pairs=method(a,prime,threshold)
     results[name]=dict(pairs=pairs,cpu=time.process_time()-tick+(frontier_cpu if name=='anchors' else 0),tests=count[0])
    # Compare every pair eligible under the conservative frontier, stronger than
    # comparing only actual records or target hits.
    if results['exhaustive']['pairs']!=results['anchors']['pairs']:
     differences+=1;save(out/'mismatch.json',dict(m=row['m'],results=results,threshold=threshold));raise AssertionError('endpoint mismatch')
    hits={str(t):0 for t in TIERS};records=0;finds=[]
    with gmpy2.context(precision=160):
     for lo,hi in results['exhaustive']['pairs']:
      gap=hi-lo;ln=gmpy2.log(center+lo);merit=float(gmpy2.mpfr(gap)/ln);record=frontier.records.get(gap,0);improves=gap*record.denominator>record.numerator*ln if record else True
      for t in hits:hits[t]+=int(merit>=int(t))
      if improves or merit>=25:
       records+=int(improves);best=max(best,merit)
       verify_start=time.process_time();valid=moon.verify(center+lo,center+hi);common['verification_cpu']+=time.process_time()-verify_start
       finds.append(dict(gap=gap,merit=merit,expression=f"{row['m']}*1439#/2310{lo:+d}",record_candidate=bool(improves),verified=bool(valid),verification='BPSW endpoints plus independent next_prime check; not a primality certificate'))
    windows+=1
    for name in totals:
     totals[name]['endpoint_cpu']+=results[name]['cpu'];totals[name]['prp_tests']+=results[name]['tests'];totals[name]['record_candidates']+=records
     for t,n in hits.items():totals[name]['gaps'][t]+=n
    event=dict(round=rounds,m=row['m'],minimum_gap=threshold,survivors=len(a),policies=results,record_candidates=records,gaps=hits)
    with (out/'windows.jsonl').open('a') as f:f.write(json.dumps(event)+'\n')
    if finds:
     with (out/'finds.jsonl').open('a') as f:
      for found in finds:f.write(json.dumps(found)+'\n')
    checkpoint()
   print('round',rounds,'matched windows',windows,'tests',{p:x['prp_tests'] for p,x in totals.items()},flush=True)
  status='budget complete'
 except (TimeoutError,):status='budget complete or stopped; unfinished comparison censored'
 except Exception as error:status='error: '+str(error);raise
 finally:
  if worker:worker.close()
  checkpoint()
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--seconds',type=int,default=600);p.add_argument('--output',type=Path,default=Path('build/endpoint-anchors-20261102'));args=p.parse_args()
 if not 1<=args.seconds<=600:p.error('seconds 1..600')
 run(args.seconds,args.output)
