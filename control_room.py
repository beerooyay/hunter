"""Loopback control room: native proxy, bounded GitHub fleet, immutable imports.
GitHub credentials stay in gh's existing credential store. No issue comments.
"""
import argparse, concurrent.futures, hashlib, io, json, os, secrets, subprocess, sys, threading, time, urllib.error, urllib.parse, urllib.request, zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from calibration import atomic_json
from optimizer.brain import train
ROOT=Path(__file__).resolve().parent
REPO='beerooyay/hunter'; REF='integrate/cached-deepening-20261102'; WORKFLOW='hunter-records.yml'
STORE=ROOT/'fleet/control'; TOKEN=secrets.token_urlsafe(32)
POOL=concurrent.futures.ThreadPoolExecutor(max_workers=1)
LOCK=threading.Lock(); CURRENT=None
PORT=8767; NATIVE=8766

def read(path,default=None):
    try:return json.loads(Path(path).read_text())
    except (OSError,ValueError):return {} if default is None else default

def gh(*args,raw=False):
    p=subprocess.run(['gh',*args],cwd=ROOT,capture_output=True,timeout=60)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace')[:800])
    return p.stdout if raw else json.loads(p.stdout or b'{}')

def api(path,*args,raw=False):return gh('api',f'repos/{REPO}/{path}',*args,raw=raw)

def extract_snapshot(blob,dest):
    allowed={'checkpoint.json','gaps.tsv','jobs.tsv','state.tsv','FOUND.tsv','VERIFIED.tsv','hunt.log','native-status.json','summary.json','model.json','prospective.json'}
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        if sum(x.file_size for x in z.infolist())>150_000_000:raise ValueError('artifact exceeds import limit')
        entries=[x for x in z.infolist() if x.filename in allowed]
        dest.mkdir(parents=True,exist_ok=True)
        hashes={}
        for item in entries:
            data=z.read(item);(dest/item.filename).write_bytes(data);hashes[item.filename]=hashlib.sha256(data).hexdigest()
        atomic_json(dest/'receipt.json',dict(imported=time.time(),sha256=hashes))

def sync():
    allruns=api('actions/runs?per_page=30')['workflow_runs']
    runs=[r for r in allruns if r.get('path')=='.github/workflows/'+WORKFLOW][:6]
    view=[]
    for r in runs:
        rid=r['id']; jobs=api(f'actions/runs/{rid}/jobs?per_page=100')['jobs']
        artifacts=api(f'actions/runs/{rid}/artifacts?per_page=100')['artifacts']
        for a in artifacts:
            if a['expired'] or a['size_in_bytes']>60_000_000 or not a['name'].startswith(('fleet-','hunter-native')) or a['name']=='fleet-native':continue
            dest=STORE/'imports'/str(rid)/str(a['id'])
            if not(dest/'receipt.json').exists():
                extract_snapshot(api(f'actions/artifacts/{a["id"]}/zip',raw=True),dest)
        checkpoints={}
        for path in (STORE/'imports'/str(rid)).glob('*/checkpoint.json'):
            item=read(path);shard=str(item.get('shard'))
            if item.get('updated',0)>checkpoints.get(shard,{}).get('updated',0):checkpoints[shard]=item
        view.append(dict(id=rid,status=r['status'],conclusion=r['conclusion'],url=r['html_url'],branch=r['head_branch'],created=r['created_at'],jobs=[{k:j.get(k) for k in ('id','name','status','conclusion','started_at','completed_at','html_url')} for j in jobs],checkpoints=list(checkpoints.values())))
    payload=dict(updated=time.time(),runs=view,error=None)
    atomic_json(STORE/'cloud.json',payload)
    return payload

def launch(workers):
    if workers not in (8,10):raise ValueError('choose 8 or 10 workers')
    repo=gh('repo','view',REPO,'--json','isPrivate')
    if repo['isPrivate']:raise ValueError('free-only control supports this public repository only')
    runs=api('actions/workflows/'+WORKFLOW+'/runs?per_page=30')['workflow_runs']
    if any(r['status']!='completed' for r in runs):raise ValueError('a fleet campaign is already active or queued')
    api('actions/workflows/'+WORKFLOW+'/dispatches','-X','POST','-f','ref='+REF,'-f',f'inputs[workers]={workers}')
    atomic_json(STORE/'last-launch.json',dict(at=time.time(),workers=workers,ref=REF))
    return dict(message=f'{workers} workers requested; GitHub may queue capacity. Refresh shortly.')

def cancel(runid):
    run=api(f'actions/runs/{int(runid)}')
    if run.get('path')!='.github/workflows/'+WORKFLOW:raise ValueError('not a Hunter fleet campaign')
    api(f'actions/runs/{int(runid)}/cancel','-X','POST')
    return {'message':'stop requested; completed checkpoints remain available'}

def training():
    paths=[ROOT/'gaps.tsv',*sorted((STORE/'imports').glob('*/*/gaps.tsv'))]
    return train(paths,ROOT/'learning/brain')

def task(name,fn):
    global CURRENT
    with LOCK:
        if CURRENT is not None and not CURRENT.done():raise ValueError('another control task is still running')
        def job():
            atomic_json(STORE/'task.json',dict(name=name,status='running',updated=time.time()))
            try:
                value=fn();atomic_json(STORE/'task.json',dict(name=name,status='complete',updated=time.time(),result=value))
            except Exception as e:
                atomic_json(STORE/'task.json',dict(name=name,status='failed',updated=time.time(),error=str(e)))
        CURRENT=POOL.submit(job)
    return {'accepted':True,'task':name}

def schedule_check():
    schedule=read(STORE/'schedule.json')
    if schedule.get('status')=='pending' and schedule['at']<=time.time():
        # Claim before sending: a crash cannot silently launch a duplicate.
        schedule['status']='claimed';atomic_json(STORE/'schedule.json',schedule)
        try:
            result=launch(schedule['workers']);schedule.update(status='launched',result=result)
        except Exception as e:schedule.update(status='failed',error=str(e))
        atomic_json(STORE/'schedule.json',schedule)

def background():
    last=0
    while True:
        try:
            if CURRENT is None or CURRENT.done():
                if read(STORE/'schedule.json').get('status')=='pending' and read(STORE/'schedule.json')['at']<=time.time(): task('scheduled launch',schedule_check)
                elif time.monotonic()-last>90:
                    task('cloud sync',sync);last=time.monotonic()
        except Exception:pass
        time.sleep(5)

def status():
    prospective=[read(p) for p in (STORE/'imports').glob('*/*/prospective.json')]
    prospective.sort(key=lambda x:x.get('updated',0),reverse=True)
    return dict(prospective=prospective[:3],cloud=read(STORE/'cloud.json'),brain=read(ROOT/'learning/brain/summary.json'),experiments=read(ROOT/'optimizer/experiments.json'),task=read(STORE/'task.json'),schedule=read(STORE/'schedule.json'),token=TOKEN,ref=REF)

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*a):pass
    def send(self,data,ctype='application/json',status=200,headers=None):
        if not isinstance(data,bytes):data=json.dumps(data).encode()
        self.send_response(status);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store')
        for k,v in (headers or {}).items():self.send_header(k,v)
        self.end_headers();self.wfile.write(data)
    def valid_host(self):return self.headers.get('Host') in (f'localhost:{PORT}',f'127.0.0.1:{PORT}')
    def do_GET(self):
        if not self.valid_host():return self.send({'error':'loopback host required'},status=403)
        path=urllib.parse.urlsplit(self.path).path
        if path=='/control/status':return self.send(status())
        if path.startswith('/control/export/'):
            kind=path.rsplit('/',1)[1]
            if kind=='brain':data=read(ROOT/'learning/brain/summary.json')
            elif kind=='model':data=read(ROOT/'learning/brain/model.json')
            elif kind=='fleet':data=read(STORE/'cloud.json')
            elif kind=='experiments':data=read(ROOT/'optimizer/experiments.json')
            elif kind=='records':
                lines={}
                for p in [ROOT/'FOUND.tsv',*sorted((STORE/'imports').glob('*/*/FOUND.tsv'))]:
                    if p.exists():
                        for l in p.read_text().splitlines():
                            f=l.split('\t')
                            if len(f)>=3:lines.setdefault((f[0],f[2]),l)
                return self.send(('\n'.join(lines[k] for k in sorted(lines))+'\n').encode(),'text/tab-separated-values',headers={'Content-Disposition':'attachment; filename="hunter-candidates.tsv"'})
            else:return self.send({'error':'unknown export'},status=404)
            return self.send(data,headers={'Content-Disposition':f'attachment; filename="hunter-{kind}.json"'})
        if path=='/':return self.send((ROOT/'ui.html').read_bytes(),'text/html; charset=utf-8')
        if path=='/control.js':return self.send((ROOT/'control.js').read_bytes(),'text/javascript')
        if path=='/frontier.css':return self.send((ROOT/'frontier.css').read_bytes(),'text/css')
        return self.proxy()
    def do_POST(self):
        if not self.valid_host() or self.headers.get('X-Hunter-Control')!=TOKEN:return self.send({'error':'control token required'},status=403)
        if self.headers.get('Origin') not in (None,f'http://localhost:{PORT}',f'http://127.0.0.1:{PORT}'):return self.send({'error':'origin rejected'},status=403)
        length=int(self.headers.get('Content-Length','0'))
        if length>8192:return self.send({'error':'request too large'},status=413)
        body=self.rfile.read(length)
        if not self.path.startswith('/control/'):return self.proxy(body)
        try:
            data=json.loads(body or b'{}');action=self.path.rsplit('/',1)[1]
            if action=='sync':result=task('cloud sync',sync)
            elif action=='train':result=task('Praetor training',training)
            elif action=='launch':result=task('launch fleet',lambda:launch(int(data['workers'])))
            elif action=='stop':result=task('stop fleet',lambda:cancel(int(data['run'])))
            elif action=='schedule':
                at=float(data['at']);workers=int(data['workers'])
                if not(time.time()+30<=at<=time.time()+172800) or workers not in (8,10):raise ValueError('schedule within 48 hours; 8 or 10 workers')
                result=dict(at=at,workers=workers,status='pending');atomic_json(STORE/'schedule.json',result)
            elif action=='unschedule':result={'status':'cancelled'};atomic_json(STORE/'schedule.json',result)
            else:raise ValueError('unknown action')
            self.send(result)
        except (ValueError,KeyError,TypeError) as e:self.send({'error':str(e)},status=400)
    def proxy(self,body=None):
        # Native server has a fixed route allowlist and never sees GitHub credentials.
        try:
            request=urllib.request.Request(f'http://127.0.0.1:{NATIVE}'+self.path,data=body,headers={'Content-Type':'application/x-www-form-urlencoded'})
            with urllib.request.urlopen(request,timeout=20) as r:
                headers={k:r.headers[k] for k in ('X-File-Size',) if k in r.headers}
                self.send(r.read(),r.headers.get('Content-Type','application/json'),r.status,headers)
        except urllib.error.HTTPError as e:self.send(e.read(),status=e.code)
        except OSError:self.send({'error':'native hunter offline'},status=503)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8767);parser.add_argument('--native-port',type=int,default=8766);a=parser.parse_args();PORT=a.port;NATIVE=a.native_port
    STORE.mkdir(parents=True,exist_ok=True)
    threading.Thread(target=background,daemon=True).start()
    print(f'control room: http://127.0.0.1:{PORT}',flush=True)
    ThreadingHTTPServer(('127.0.0.1',PORT),Handler).serve_forever()
