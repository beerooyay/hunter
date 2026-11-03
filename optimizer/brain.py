"""Dataset/provenance adapter; forward pass and SGD run in native Praetor.
Predicts log endpoint elapsed time conditional on the current stopping policy.
Unfinished gaps remain cost observations, never negative rare-gap labels.
"""
import argparse, hashlib, json, math, os, random, re, subprocess, time
from pathlib import Path
from calibration import atomic_json
ROOT=Path(__file__).resolve().parents[1]
VERSION='praetor-cost-mlp-v1'
Q=65536

def norm(seconds): return min(1.,max(0.,math.log1p(seconds)/math.log(301)))
def dataset(paths):
    rows={}; skipped=0; sources=[]
    for path in sorted(map(Path,paths)):
        if not path.is_file(): continue
        digest=hashlib.sha256()
        with path.open('rb') as stream:
            for raw in stream:
                digest.update(raw)
                try:
                    f=raw.decode().strip().split('\t'); match=re.fullmatch(r'P(\d+)_d(\d+)_L1e9',f[0])
                    if not match or len(f)<21: continue
                    p,d=map(int,match.groups()); m=int(f[1]); observed=float(f[16]); expected=float(f[20]); q=float(f[18]); digits=int(f[2])
                    if not all(map(math.isfinite,[observed,expected,q])) or min(observed,expected)<=0 or not 0<q<1: raise ValueError()
                    identity=f'{p}:{d}:{m}'
                    # Whole nearby multiplier blocks stay together across all input files.
                    block=f'{p}:{d}:{m//10000}'
                    bucket=int(hashlib.sha256(block.encode()).hexdigest()[:8],16)%10
                    split=2 if bucket==0 else 1 if bucket==1 else 0
                    x=[1.,min(p/16000,1),d/2310,min(digits/7000,1),min(q*1000,1),norm(expected)]
                    rows.setdefault(identity,dict(id=identity,block=block,split=split,x=[round(v*Q) for v in x],y=round(norm(observed)*Q),completed=f[5]=='1',hit=f[15]=='1'))
                except (ValueError,IndexError,UnicodeError): skipped+=1
        sources.append(dict(name=path.name,sha256=digest.hexdigest()))
    result=list(rows.values()); random.Random(991).shuffle(result)
    return result[:200000],sources,skipped

def train(paths,output,binary=ROOT/'hunter'):
    tick=time.monotonic(); rows,sources,skipped=dataset(paths); output=Path(output);output.mkdir(parents=True,exist_ok=True)
    if not rows: raise ValueError('no valid volume cost observations available')
    wire=str(len(rows))+'\n'+''.join(' '.join(map(str,[r['split'],*r['x'],r['y']]))+'\n' for r in rows)
    result=subprocess.run([str(binary),'brain-train'],input=wire,text=True,capture_output=True,timeout=120,check=True)
    predictions={}; weights=None
    for line in result.stdout.splitlines():
        f=line.split('\t')
        if f[0]=='P': predictions[int(f[1])]=int(f[2])/Q
        elif f[0]=='W': weights=list(map(int,f[1:]))
    if len(predictions)!=len(rows) or weights is None or len(weights)!=57: raise RuntimeError('incomplete native model output')
    metrics={}
    training_rows=[r for r in rows if r["split"]==0]
    shift=sum((r["y"]-r["x"][5])/Q for r in training_rows)/max(1,len(training_rows))
    for split,name in enumerate(('train','validation','test')):
        ix=[i for i,r in enumerate(rows) if r['split']==split]
        base=sum((rows[i]['x'][5]/Q-rows[i]['y']/Q)**2 for i in ix)/max(1,len(ix))
        mse=sum((predictions[i]-rows[i]['y']/Q)**2 for i in ix)/max(1,len(ix))
        calibrated=sum((min(1,max(0,rows[i]['x'][5]/Q+shift))-rows[i]['y']/Q)**2 for i in ix)/max(1,len(ix))
        metrics[name]=dict(calibrated_baseline_mse=calibrated,gain_vs_calibrated=1-mse/calibrated if calibrated else None,n=len(ix),blocks=len({rows[i]['block'] for i in ix}),baseline_mse=base,model_mse=mse,relative_gain=1-mse/base if base else None)
    code_hash=hashlib.sha256((ROOT/'src/brain.lang').read_bytes()+Path(__file__).read_bytes()).hexdigest()
    identity=hashlib.sha256((VERSION+code_hash+wire).encode()).hexdigest()
    snapshot=output/'versions'/identity;snapshot.mkdir(parents=True,exist_ok=True)
    model=dict(code_hash=code_hash,calibration_shift=shift,version=VERSION,id=identity,architecture='6 → 8 ReLU → residual scalar; Q16',weights=weights,implementation='Praetor forward and backprop; Python data adapter',features=['bias','P/16000','d/2310','digits/7000','q*1000','log1p(predicted_seconds)/log(301)'],target='log1p(observed_endpoint_seconds)/log(301)',mode='shadow',production_enabled=False)
    summary=dict(version=VERSION,id=identity,updated=time.time(),mode='shadow',architecture=model['architecture'],rows=len(rows),skipped=skipped,metrics=metrics,sources=sources,elapsed_s=time.monotonic()-tick,completed=sum(r['completed'] for r in rows),censored=sum(not r['completed'] for r in rows),note='Cost prediction only, conditional on existing search policy. No record pruning or tail probability claims. Block-held-out data; prospective fleet validation still required.',speedup=None)
    atomic_json(snapshot/'model.json',model);atomic_json(snapshot/'summary.json',summary)
    atomic_json(output/'model.json',model);atomic_json(output/'summary.json',summary)
    with (snapshot/'predictions.jsonl').open('w') as stream:
        for i,r in enumerate(rows): stream.write(json.dumps(dict(id=r['id'],block=r['block'],split=r['split'],observed=r['y']/Q,baseline=r['x'][5]/Q,predicted=predictions[i],completed=r['completed']))+'\n')
    return summary

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,action='append');p.add_argument('--output',type=Path,default=ROOT/'learning/brain');a=p.parse_args()
    print(json.dumps(train(a.input or [ROOT/'gaps.tsv'],a.output),indent=2))
