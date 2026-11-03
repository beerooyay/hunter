"""Prospective frozen-model evaluation. Never fit on the new campaign here."""
import json, subprocess, time
from pathlib import Path
from optimizer.brain import ROOT,Q,dataset
from calibration import atomic_json

def evaluate(paths,output,model_path=ROOT/'optimizer/seed-model.json'):
    rows,sources,skipped=dataset(paths);model=json.loads(Path(model_path).read_text())
    if not rows:raise ValueError('no fresh observations')
    wire=str(len(rows))+'\n'+''.join(' '.join(map(str,[r['split'],*r['x'],r['y']]))+'\n' for r in rows)
    wire+=' '.join(str(w%(2**64)) for w in model['weights'])+'\n'
    p=subprocess.run([str(ROOT/'hunter'),'brain-train','predict'],input=wire,text=True,capture_output=True,check=True,timeout=60)
    predictions=[int(line.split('\t')[2])/Q for line in p.stdout.splitlines() if line.startswith('P\t')]
    if len(predictions)!=len(rows):raise ValueError('incomplete predictions')
    def mse(pred):return sum((v-r['y']/Q)**2 for v,r in zip(pred,rows))/len(rows)
    base=mse([r['x'][5]/Q for r in rows]);cal=mse([min(1,max(0,r['x'][5]/Q+model['calibration_shift'])) for r in rows]);error=mse(predictions)
    result=dict(updated=time.time(),model_id=model['id'],n=len(rows),baseline_mse=base,calibrated_mse=cal,model_mse=error,gain_vs_calibrated=1-error/cal if cal else None,sources=sources,note='Frozen historical model; entirely fresh campaign, no refitting before evaluation. Different hardware may shift elapsed costs. No measured production speedup.')
    atomic_json(Path(output),result);return result

if __name__=='__main__':evaluate(list(Path('fleet-input').rglob('gaps.tsv')),Path('brain-output/prospective.json'))
