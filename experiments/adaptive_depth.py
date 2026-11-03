"""Actual staged sieving, fixed rankings, shared endpoint-cost replay."""
import argparse,json,math,os,random,shutil,signal,subprocess,sys,time,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import gmpy2,moon
from merit_shadow import pair_score,save
from persistent_probe import ProbeWorker
TIERS=(5,10,15,20,25,30,40)
def run(seconds,folder,cached=False):
 root=Path(__file__).resolve().parents[1];folder=folder.resolve();folder.mkdir(parents=True,exist_ok=True)
 if (folder/'manifest.json').exists():raise RuntimeError('fresh output folder required')
 for n in ('hunter','records.txt','moon.py'):shutil.copy2(root/n,folder/n)
 (folder/'source').mkdir(exist_ok=True)
 for source in (root/'src/hunter.lang',root/'rt/hunter_rt.c'):
  shutil.copy2(source,folder/'source'/source.name)
 for p in (Path(__file__),Path(__file__).with_name('merit_shadow.py'),Path(__file__).with_name('persistent_probe.py')):shutil.copy2(p,folder/p.name)
 manifest=dict(started=time.time(),seconds=seconds,seed=20261103,P=1439,d=2310,target=25,shallow=1000000,deep=10000000,raw_centers=256,deepen_fraction=.3,final_fraction=.1,binary_sha256=hashlib.sha256((folder/'hunter').read_bytes()).hexdigest(),scope='Baseline deep-sieves all windows; adaptive shallow-sieves all and deep-sieves only top30%. Both rank with the same pair operator and select the same number of final windows. Native setup and actual subprocess CPU/wall times included. Endpoint outcomes/timings shared in replay, not independent end-to-end throughput runs. Adaptive deep calls currently rebuild setup per window; no caching speedup assumed.')
 manifest['cached_incremental_batch']=cached
 if cached:manifest['scope']='Native persistent workers retain primes, primorial residues, scratch buffers and shallow batch bitsets. Selected windows are incrementally deepened in one request using only added primes. Baseline uses its own persistent worker. Setup costs and IPC/parse CPU are charged. Shared endpoint timings remain replay costs, not independent runtime trials.'
 save(folder/'manifest.json',manifest);os.nice(10);deadline=time.monotonic()+seconds;rng=random.Random(manifest['seed']);events=[];rounds=0;windows=0;best=0;status='running'
 totals={p:dict(sieve_cpu=0.,sieve_wall=0.,score_cpu=0.,endpoint_cpu=0.,selected_windows=0,gaps={str(t):0 for t in TIERS}) for p in ('full','adaptive')}
 workers={};overlap=baseline_n=0;retained={str(t):0 for t in TIERS}
 def checkpoint():save(folder/'summary.json',dict(status=status,updated=time.time(),rounds=rounds,unique_windows=windows,best_merit=best,policies=totals,selected_overlap=overlap,full_selected=baseline_n,baseline_hits_retained=retained,sieve_cpu_speedup=totals['full']['sieve_cpu']/totals['adaptive']['sieve_cpu'] if totals['adaptive']['sieve_cpu'] else None,scope=manifest['scope']))
 def stop(signum,frame):raise TimeoutError('stop requested')
 signal.signal(signal.SIGTERM,stop)
 def probe(start,count,depth,label,selected=None):
  if time.monotonic()>=deadline:raise TimeoutError
  if cached:
   policy='full' if label=='full' else 'adaptive'
   rows,cpu,wall,text=workers[policy].probe(start,count,depth,selected)
   (folder/f'{rounds:04d}-{label}.tsv').write_text(text)
   return rows,cpu,wall
  u=os.times();clock=time.monotonic()
  p=subprocess.run([str(folder/'hunter'),'probe','1439','2310',str(count),'25',str(start),str(depth)],cwd=folder,env=dict(os.environ,HUNTER_PATTERNS='1'),capture_output=True,text=True,check=True,timeout=max(.01,deadline-time.monotonic()))
  after=os.times();cpu=after.children_user+after.children_system-u.children_user-u.children_system;wall=time.monotonic()-clock
  (folder/f'{rounds:04d}-{label}.tsv').write_text(p.stdout)
  return moon.parse(p.stdout),cpu,wall
 def ranked(rows):
  return sorted(rows,key=lambda r:(pair_score(r['q'],math.ceil(25*r['ln']),[-x for x in reversed(r['left'])]+r['right']),r['m']),reverse=True)
 checkpoint()
 try:
  if cached:
   for policy in totals:
    workers[policy]=ProbeWorker(folder/'hunter',folder,deadline)
    totals[policy]['sieve_cpu']+=workers[policy].setup_cpu
    totals[policy]['sieve_wall']+=workers[policy].setup_wall
  while time.monotonic()<deadline:
   rounds+=1;start=rng.randrange(10000000,900000000000)|1
   shallow,sc,sw=probe(start,256,1000000,'shallow');tick=time.process_time();short=ranked(shallow)[:math.ceil(.3*len(shallow))];asc=time.process_time()-tick
   refined=[];dc=dw=0
   # Alternate independent deep-stage execution order to reduce fixed order bias.
   def deep_shortlist():
    nonlocal dc,dw
    if cached:
     rs,c,w=probe(start,256,10000000,'adaptive-batch',sorted(row['m']-start for row in short));refined.extend(rs);dc+=c;dw+=w
     return
    for row in short:
     rs,c,w=probe(row['m'],1,10000000,f"adaptive-{row['m']}");refined.extend(rs);dc+=c;dw+=w
   if rounds%2:
    deep_shortlist();full,fc,fw=probe(start,256,10000000,'full')
   else:
    full,fc,fw=probe(start,256,10000000,'full');deep_shortlist()
   by_m={r['m']:r for r in full}
   for row in refined:
    reference=by_m[row['m']]
    assert all(row[k]==reference[k] for k in ('right','left','q','ln')),'deep subset mismatch'
   keep=max(1,math.ceil(.1*len(full)));tick=time.process_time();fsel=ranked(full)[:keep];fscore=time.process_time()-tick;tick=time.process_time();asel=ranked(refined)[:keep];ascore=asc+time.process_time()-tick
   chosen={'full':{r['m'] for r in fsel},'adaptive':{r['m'] for r in asel}}
   totals['full']['sieve_cpu']+=fc;totals['full']['sieve_wall']+=fw;totals['full']['score_cpu']+=fscore
   totals['adaptive']['sieve_cpu']+=sc+dc;totals['adaptive']['sieve_wall']+=sw+dw;totals['adaptive']['score_cpu']+=ascore
   overlap+=len(chosen['full']&chosen['adaptive']);baseline_n+=keep
   save(folder/f'{rounds:04d}-selection.json',dict(start=start,deepened=[r['m'] for r in refined],selected={p:sorted(ms) for p,ms in chosen.items()},full_sieve_cpu=fc,adaptive_sieve_cpu=sc+dc,full_sieve_wall=fw,adaptive_sieve_wall=sw+dw))
   union=list(set.union(*chosen.values()));rng.shuffle(union);base=gmpy2.primorial(1439)//2310
   for m in union:
    row=by_m[m];center=base*m;primes=[];tick=time.process_time()
    for x in [-v for v in reversed(row['left'])]+row['right']:
     if time.monotonic()>=deadline:raise TimeoutError
     if gmpy2.is_bpsw_prp(center+x):primes.append(x)
    merits=[]
    for lo,hi in zip(primes,primes[1:]):
     merit=float(gmpy2.mpfr(hi-lo)/gmpy2.log(center+lo));merits.append(merit)
     if merit>=20:
      valid=moon.verify(center+lo,center+hi)
      with (folder/'finds.jsonl').open('a') as f:f.write(json.dumps(dict(gap=hi-lo,merit=merit,verified=valid,expression=f'{m}*1439#/2310{lo:+d}'))+'\n')
    cpu=time.process_time()-tick;counts={str(t):sum(g>=t for g in merits) for t in TIERS};windows+=1;best=max([best]+merits)
    event=dict(round=rounds,m=m,cpu=cpu,gaps=counts,primes=primes,selected_by=[p for p in chosen if m in chosen[p]])
    with (folder/'windows.jsonl').open('a') as f:f.write(json.dumps(event)+'\n')
    for policy in event['selected_by']:
     totals[policy]['selected_windows']+=1;totals[policy]['endpoint_cpu']+=cpu
     for t,n in counts.items():totals[policy]['gaps'][t]+=n
    if len(event['selected_by'])==2:
     for t,n in counts.items():retained[t]+=n
    checkpoint()
   print('round',rounds,'windows',windows,'sieve CPU full/adaptive',fc,sc+dc,'selection overlap',len(chosen['full']&chosen['adaptive']),keep,flush=True)
  status='budget complete'
 except (TimeoutError,subprocess.TimeoutExpired):status='stopped or budget complete; unfinished work censored'
 except Exception as e:status='error: '+str(e);raise
 finally:
  for worker in workers.values():worker.close()
  checkpoint()
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--cached',action='store_true');p.add_argument('--seconds',type=int,default=600);p.add_argument('--output',type=Path,default=Path('build/adaptive-depth-20261102'));a=p.parse_args()
 if not 1<=a.seconds<=600:p.error('seconds 1..600')
 run(a.seconds,a.output,a.cached)
