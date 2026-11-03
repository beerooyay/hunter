"""Real native volume engine: baseline versus experimental center certificates.
Freeze per-test price to compare the same conditional policy independently of
clock jitter. This is not a live adaptive scheduler or production deployment.
"""
import argparse,json,os,subprocess,time,hashlib,sys,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import gmpy2

def run(out,seconds,ordinary_only=False):
 root=Path(__file__).resolve().parents[1];out=out.resolve();out.mkdir(parents=True,exist_ok=True)
 if (out/'manifest.json').exists():raise RuntimeError('fresh output required')
 for name in ('hunter','records.txt'):shutil.copy2(root/name,out/name)
 shutil.copy2(__file__,out/'volume_anchor_benchmark.py')
 cases=[
  ('known6007-unfiltered',6007,210,14589341,2,147416,'0',55000000,156200),
  ('known6007-priced',6007,210,14589341,2,147416,'8e-5',55000000,156200),
  ('ordinary6007',6007,210,14654393,12,147416,'8e-5',55000000,None),
  ('known6007d2310',6007,2310,20244649,2,147356,'0',55000000,148030),
  ('known8009',8009,2310,5820043,2,196909,'0',100000000,210786),
  ('ordinary8009',8009,2310,6015845,6,196909,'8e-5',100000000,None),
 ]
 if ordinary_only:cases=[c for c in cases if c[0].startswith('ordinary')]
 manifest=dict(started=time.time(),seconds=seconds,cases=cases,table_sha256=hashlib.sha256((out/'records.txt').read_bytes()).hexdigest(),binary_sha256=hashlib.sha256((out/'hunter').read_bytes()).hexdigest(),scope='Actual native volume engine at depth10^9 and production window sizes. Same externally fixed lambda and per-PRP cost in both modes; record detection and final GMP checks retained. Known discoveries are positive controls against a frozen older public table, not new records. No live scheduler claim.')
 (out/'manifest.json').write_text(json.dumps(manifest,indent=2));deadline=time.monotonic()+seconds;done=[]
 def save(status):
  summary=dict(status=status,cases=done,record_sets_preserved=all(x['records_equal'] for x in done),full_cpu=sum(x['baseline']['cpu_s'] for x in done),anchor_cpu=sum(x['anchors']['cpu_s'] for x in done))
  summary['cpu_speedup']=summary['full_cpu']/summary['anchor_cpu'] if summary['anchor_cpu'] else None
  tmp=out/'summary.tmp';tmp.write_text(json.dumps(summary,indent=2));tmp.replace(out/'summary.json')
 save('running')
 try:
  for index,(name,P,d,m,count,SL,lam,price,expected) in enumerate(cases):
   results={};commands=['baseline','anchors'] if index%2==0 else ['anchors','baseline']
   for mode in commands:
    env=dict(os.environ,HUNT_FIXED_PRP_NS=str(price));env.pop('HUNT_DRY',None);env.pop('HUNTER_GPU',None);env.pop('HUNT_RECORD_ANCHORS',None)
    if mode=='anchors':env['HUNT_RECORD_ANCHORS']='1'
    proc=subprocess.run([str(out/'hunter'),'hunt',str(P),str(d),str(m),str(count),str(SL),'1e9',lam,'15',str(out/'records.txt')],cwd=out,env=env,capture_output=True,text=True,check=True,timeout=max(.01,deadline-time.monotonic()))
    (out/f'{name}-{mode}.tsv').write_text(proc.stdout)
    stats=dict(x.split('=',1) for x in next(l for l in proc.stdout.splitlines() if l.startswith('#\t')).split('\t')[1:])
    rows=[l.split('\t') for l in proc.stdout.splitlines() if l.startswith('T\t')]
    records=sorted((int(r[1]),int(r[8]),r[9]) for r in rows if r[15]=='1')
    witnesses=[l.split('\t') for l in proc.stdout.splitlines() if l.startswith('X\t')]
    K=gmpy2.primorial(P)//d
    for row in witnesses:
     _,mm,G,left,right=row;mm,G,left,right=map(int,(mm,G,left,right));N=K*mm
     assert left+right<G
     assert gmpy2.is_bpsw_prp(N-left) and gmpy2.is_bpsw_prp(N+right)
    results[mode]=dict(cpu_s=float(stats['cpu_s']),test_s=float(stats['test_s']),sieve_s=float(stats['sieve_s']),score_s=float(stats['score_s']),records=records,certified_skips=len(witnesses),summary=stats)
   assert results['baseline']['records']==results['anchors']['records'],name
   if expected is not None:
    assert any(gap==expected for mm,gap,merit in results['baseline']['records']),f'positive control not reached: {name}'
   done.append(dict(name=name,records_equal=True,baseline=results['baseline'],anchors=results['anchors']));save('running')
   print(name,'baseline CPU',results['baseline']['cpu_s'],'anchor CPU',results['anchors']['cpu_s'],'records',results['baseline']['records'],'skips',results['anchors']['certified_skips'],flush=True)
  save('complete')
 except subprocess.TimeoutExpired:save('budget exhausted; unpaired case excluded')
 except Exception as error:save('error: '+str(error));raise
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--ordinary-only',action='store_true');p.add_argument('--seconds',type=int,default=600);p.add_argument('--output',type=Path,default=Path('build/volume-anchor-20261102'));a=p.parse_args();run(a.output,a.seconds,a.ordinary_only)
