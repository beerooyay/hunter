#!/usr/bin/env python3
"""hunter_ui.py -- the gap hunter's control room. stdlib only.

    python3 hunter_ui.py            then open http://localhost:8765

start / stop hunts, watch every core live, see records the moment they land (verified in the
background), check them against the live record table, copy submission lines, and see whether the
model is still telling the truth. closing this window does NOT stop a running hunt.
"""
import json, math, os, re, shutil, subprocess, sys, threading, time, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
P_ = lambda n: os.path.join(HERE, n)
sys.path.insert(0, HERE)
import brain  # reuse posterior / arm definitions

PORT = int(os.environ.get('HUNTER_PORT', 8765))
CFG_F, SUB_F, TABLE_F, PID_F, LOG_F = P_('ui_config.json'), P_('submitted.json'), P_('table_check.json'), P_('brain.pid'), P_('hunt.log')
MERTENS_1E9 = 0.027093154870   # prod_{p<=1e9} (1 - 1/p), computed exactly
_lnk_cache, _gap_cache = {}, {'size': -1, 'data': None}

def jload(path, default):
    try: return json.load(open(path))
    except Exception: return default

def jsave(path, obj):
    tmp = path + '.tmp'; json.dump(obj, open(tmp, 'w'), indent=1); os.replace(tmp, path)

def cfg(): return dict(dict(discoverer='B.Rouyea'), **jload(CFG_F, {}))

def lnk(P, d):
    k = (P, d)
    if k not in _lnk_cache: _lnk_cache[k] = brain.lnK(P, d)
    return _lnk_cache[k]

def brain_alive():
    pid = jload(PID_F, {}).get('pid')
    if not pid: return False
    try:
        os.kill(pid, 0)
        st = jload(brain.STATUS, {})
        return bool(st.get('running', True))
    except Exception:
        return False

def parse_arm(key):
    m = re.fullmatch(r'P(\d+)_d(\d+)_L(.+)', key)
    return (int(m.group(1)), int(m.group(2)), m.group(3)) if m else None

def model_check():
    """survivor-model calibration from gaps.tsv: geometric MLE of q on each side + PIT tails + near misses."""
    try: size = os.path.getsize(brain.GAPS)
    except OSError: return None
    if _gap_cache['size'] == size: return _gap_cache['data']
    nR = sR = nL = sL = 0; qsum = 0.0; eR = eL = 0.0; pitR = [0, 0, 0, 0]; pitL = [0, 0, 0, 0]; near = []; merits = []
    thr = (0.5, 0.1, 0.01, 0.001)
    for line in open(brain.GAPS):
        f = line.rstrip('\n').split('\t')
        if len(f) < 17: continue
        pa = parse_arm(f[0])
        if not pa: continue
        P, d, L = pa
        if len(f) > 18:
            q = float(f[18])
        else:
            prod = MERTENS_1E9 if L == '1e9' else math.exp(-0.5772156649) / math.log(float(L))
            q = 1 / ((lnk(P, d) + math.log(int(f[1]))) * prod)
        tr, tl = int(f[11]), int(f[12])
        if int(f[7]) > 0:
            nR += 1; sR += tr; qsum += q; eR += 1 / q
            u = (1 - q) ** (tr - 1)
            for i, t in enumerate(thr): pitR[i] += u < t
        if f[5] == '1':
            nL += 1; sL += tl; eL += 1 / q
            u = (1 - q) ** (tl - 1)
            for i, t in enumerate(thr): pitL[i] += u < t
            merit, rec = float(f[9]), float(f[10])
            merits.append(merit)
            if rec > 0: near.append((merit / rec, int(f[8]), merit, rec, f[0], f[15] == '1'))
    near.sort(reverse=True)
    qm = qsum / nR if nR else 0
    hist = [0] * 30
    for m in merits: hist[min(29, int(m))] += 1
    data = dict(
        nR=nR, nL=nL, q_model=qm,
        # measured / model probability that a survivor is prime, pooled across setups:
        # expected number of tests to the first prime is 1/q, so ratio = sum(1/q) / sum(tests)
        ratioR=eR / sR if sR else None, errR=1 / math.sqrt(nR) if nR else None,
        ratioL=eL / sL if sL else None, errL=1 / math.sqrt(nL) if nL else None,
        pitR=[c / nR if nR else 0 for c in pitR], pitL=[c / nL if nL else 0 for c in pitL], thr=thr,
        near=[dict(ratio=r, gap=g, merit=m, rec=rc, arm=a, hit=h) for r, g, m, rc, a, h in near[:12]],
        hist=hist)
    _gap_cache.update(size=size, data=data)
    return data

def found_rows():
    ver = {}
    if os.path.exists(brain.VERIFIED):
        for l in open(brain.VERIFIED):
            f = l.rstrip('\n').split('\t')
            if len(f) >= 4: ver[f[2]] = f[3]
    sub = set(map(str, jload(SUB_F, [])))
    table = jload(TABLE_F, {})
    me = cfg()['discoverer']
    rows, seen = [], set()
    if os.path.exists(brain.FOUND):
        for l in open(brain.FOUND):
            f = l.rstrip('\n').split('\t')
            if len(f) < 3 or not f[0].isdigit(): continue
            gap, merit, expr = f[0], float(f[1]), f[2]
            if expr in seen: continue
            seen.add(expr)
            old = f[3].split('=')[-1] if len(f) > 3 else ''
            t = table.get('gaps', {}).get(gap)
            if t is None: tstat = 'unchecked'
            elif t['who'] == me and abs(t['merit'] - merit) < 2e-3: tstat = 'on the table'
            elif t['merit'] > merit + 1e-4: tstat = 'beaten'
            elif gap in sub: tstat = 'submitted, waiting'
            else: tstat = 'open: submit it'
            rows.append(dict(gap=int(gap), merit=merit, expr=expr, old=old, when=f[4] if len(f) > 4 else '',
                             verified=ver.get(expr, 'pending'), table=tstat,
                             table_holder=(t or {}).get('who'), table_merit=(t or {}).get('merit')))
    return rows

def status():
    st = jload(brain.STATE, {'arms': {}})
    live = jload(brain.STATUS, {})
    alive = brain_alive()
    arms = []
    for s in st.get('arms', {}).values():
        s.setdefault('logs', []); s.setdefault('prior', None); s.setdefault('secs', 0); s.setdefault('value', 0)
    scale = brain.price_scale(st)
    shown = {brain.arm_key(a) for a in jload(brain.ARMS_FILE, brain.DEFAULT_ARMS)}
    for k, s in st.get('arms', {}).items():
        if k not in shown and not s.get('secs'): continue
        mu, v = brain.posterior(s, scale)
        unpriced = not s['prior'] and not s['logs']
        arms.append(dict(key=k, est=None if unpriced else math.exp(mu + v / 2) * 3600, lo=math.exp(mu - 1.64 * math.sqrt(v)) * 3600,
                         hi=math.exp(mu + 1.64 * math.sqrt(v)) * 3600, prior=(s['prior'] or 0) * 3600 * scale,
                         jobs=s.get('jobs', len(s['logs'])), coreh=s.get('secs', 0) / 3600, tested=s.get('tested', 0),
                         hits=s.get('hits', 0), value=s.get('value', 0), pcal=s.get('pcal', 0), calhits=s.get('calhits', 0)))
    for a in arms:
        if a['est'] is None: a['lo'] = a['hi'] = None
    arms.sort(key=lambda a: -(a['est'] or 0))
    jobs = []
    for fn in ('batches.jsonl', 'jobs.jsonl'):
        if os.path.exists(P_(fn)):
            for l in open(P_(fn)):
                try:
                    r = json.loads(l)
                    if r.get('kind', 'job') == 'job': jobs.append(dict(t=r['t'], arm=r['arm'], rate=r['rate'] * 3600))
                except Exception: pass
    found = found_rows()
    coreh = sum(a['coreh'] for a in arms)
    log = open(LOG_F).read().splitlines()[-60:] if os.path.exists(LOG_F) else []
    return dict(now=time.time(), alive=alive, live=live if alive else dict(live, workers={}), cfg=cfg(),
                arms=arms, jobs=jobs[-600:], found=found, coreh=coreh,
                expected=sum(a['value'] for a in arms), tested=sum(a['tested'] for a in arms),
                lam=st.get('lambda', 0) * 3600, model=model_check(), log=log,
                table_checked=jload(TABLE_F, {}).get('t'), cpu=os.cpu_count(),
                default_arms=[brain.arm_key(a) for a in brain.DEFAULT_ARMS],
                current_arms=[brain.arm_key(a) for a in jload(brain.ARMS_FILE, brain.DEFAULT_ARMS)])

def start(body):
    if brain_alive(): return dict(ok=False, msg='a hunt is already running')
    keys = body.get('arms') or []
    arms = []
    for k in keys:
        pa = parse_arm(k)
        if pa: arms.append(dict(P=pa[0], d=pa[1], L=pa[2], slf=25, mcal=15))
    if not arms: arms = brain.DEFAULT_ARMS
    jsave(brain.ARMS_FILE, arms)
    hours = float(body.get('hours', 8)); cores = int(body.get('cores', max(1, (os.cpu_count() or 2) - 2)))
    cmd = [sys.executable, '-u', P_('brain.py'), '--hours', str(hours), '--cores', str(cores),
           '--job-secs', str(float(body.get('job_secs', 600)))]
    if shutil.which('caffeinate'): cmd = ['caffeinate', '-i'] + cmd      # keep the mac awake
    logf = open(LOG_F, 'a'); logf.write(f"\n==== hunt started {time.strftime('%Y-%m-%d %H:%M')} hours={hours} cores={cores} ====\n"); logf.flush()
    p = subprocess.Popen(cmd, cwd=HERE, stdout=logf, stderr=subprocess.STDOUT, start_new_session=True)
    jsave(PID_F, dict(pid=p.pid, t=time.time()))
    return dict(ok=True, msg=f'hunt started on {cores} cores for {hours:g} h')

def stop(body):
    open(brain.STOPF, 'w').write('now' if body.get('now') else 'graceful')
    return dict(ok=True, msg='stopping now' if body.get('now') else 'stopping after current jobs finish')

def check_table(_):
    try:
        txt = urllib.request.urlopen('https://primegaps.cloudygo.com/merits.txt', timeout=60).read().decode()
    except Exception as e:
        return dict(ok=False, msg=f'could not reach the record table: {e}')
    want = {str(r['gap']) for r in found_rows()}
    gaps = {}
    for line in txt.splitlines():
        f = line.split()
        if len(f) >= 3 and f[0] in want:
            gaps[f[0]] = dict(merit=float(f[1]), who=f[2])
    jsave(TABLE_F, dict(t=time.time(), gaps=gaps))
    return dict(ok=True, msg=f'checked {len(want)} gaps against the live table')

def run_script(name):
    r = subprocess.run([sys.executable, P_(name)], cwd=HERE, capture_output=True, text=True, timeout=3600)
    return (r.stdout + r.stderr).strip()[-2000:]

def update_records(_):
    return dict(ok=True, msg=run_script('update_records.py'))

def verify(_):
    threading.Thread(target=lambda: run_script('verify.py'), daemon=True).start()
    return dict(ok=True, msg='verifying unverified records in the background')

def mark_submitted(body):
    sub = set(map(str, jload(SUB_F, [])))
    sub |= set(map(str, body.get('gaps', [])))
    jsave(SUB_F, sorted(sub, key=int))
    return dict(ok=True, msg=f"marked {len(body.get('gaps', []))} as submitted")

def set_cfg(body):
    c = cfg(); c.update({k: v for k, v in body.items() if k in ('discoverer',)}); jsave(CFG_F, c)
    return dict(ok=True, msg='saved')

POST = {'/api/start': start, '/api/stop': stop, '/api/check-table': check_table, '/api/update-records': update_records,
        '/api/verify': verify, '/api/submitted': mark_submitted, '/api/config': set_cfg}

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def send(self, code, body, ctype='application/json'):
        b = body if isinstance(body, bytes) else body.encode()
        self.send_response(code); self.send_header('Content-Type', ctype); self.send_header('Content-Length', str(len(b)))
        self.send_header('Cache-Control', 'no-store'); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if self.path in ('/', '/index.html'):
            return self.send(200, open(P_('ui.html'), 'rb').read(), 'text/html; charset=utf-8')
        if self.path == '/favicon.ico':
            return self.send(204, b'', 'image/x-icon')
        if self.path.startswith('/api/status'):
            try: return self.send(200, json.dumps(status()))
            except Exception as e: return self.send(500, json.dumps(dict(error=str(e))))
        self.send(404, '{}')
    def do_POST(self):
        fn = POST.get(self.path)
        if not fn: return self.send(404, '{}')
        n = int(self.headers.get('Content-Length') or 0)
        body = json.loads(self.rfile.read(n) or b'{}')
        try: self.send(200, json.dumps(fn(body)))
        except Exception as e: self.send(500, json.dumps(dict(ok=False, msg=str(e))))

if __name__ == '__main__':
    srv = ThreadingHTTPServer(('127.0.0.1', PORT), H)
    print(f'gap hunter control room: http://localhost:{PORT}   (ctrl-c closes the page server; a running hunt keeps going)')
    if sys.platform == 'darwin' and '--no-open' not in sys.argv:
        subprocess.Popen(['open', f'http://localhost:{PORT}'])
    try: srv.serve_forever()
    except KeyboardInterrupt: pass
