#!/usr/bin/env python3
"""brain.py -- the learning half of the rb labs gap hunter (v3).

what it decides: WHERE to hunt (primorial size P, divisor d) and HOW PICKY to be (lambda).

v3 changes, all driven by the first 10 core-hours of real data:
  * continuous worker pool. every core pulls its own job and starts the next one the moment it
    finishes -- no more batch barrier where 13 cores wait for the slowest one.
  * bigger jobs (~10 min each). the fixed cost of a hunt process (primes to 1e9 + residues +
    one pass of the modular search) was 35% of all time with 90-second batches; ~3% now.
  * free exploration. the survivor model was measured to be calibrated to ~1% on real 1,707-digit
    data, so an arm can be priced with a sieve-only dry run (no prime tests) before any real work.
    those dry-run prices seed the thompson-sampling prior; real jobs then refine it.
  * policy-aware testing (inside hunt): a center is tested only if the value of the exact
    "find next prime, then continue left only if still worth it" policy beats lambda * its cost.
  * live: every tested center is streamed to gaps.tsv the moment it finishes, records are written
    to FOUND.tsv and verified in the background immediately, and status.json feeds the dashboard.

usage:
  python3 hunter_ui.py                         # the dashboard (recommended): start/stop from the browser
  python3 brain.py --hours 8 --cores 14        # or run headless
  touch STOP                                   # graceful stop (finish running jobs); 'echo now > STOP' kills them
"""
import argparse, json, math, os, random, signal, subprocess, sys, threading, time

HERE = os.path.dirname(os.path.abspath(__file__))
P_ = lambda n: os.path.join(HERE, n)
STATE, JOBS, GAPS, FOUND, VERIFIED = P_('hunt_state.json'), P_('jobs.jsonl'), P_('gaps.tsv'), P_('FOUND.tsv'), P_('VERIFIED.tsv')
STATUS, STOPF, RECORDS, HUNT, ARMS_FILE = P_('status.json'), P_('STOP'), P_('records.txt'), P_('hunt'), P_('arms.json')

# survey (policy-aware dry runs): d=210 beat 2310 beat 30030 at every size tested; sizes 1.7k-5k digits are close.
DEFAULT_ARMS = [dict(P=P, d=d, L='1e9', slf=25, mcal=15)
                for P in (4001, 6007, 8009, 12007) for d in (210, 2310)]

LOCK = threading.Lock()

def lnK(P, d):
    s, sieve = 0.0, bytearray([1]) * (P + 1)
    for i in range(2, P + 1):
        if sieve[i]:
            s += math.log(i)
            for j in range(i * i, P + 1, i): sieve[j] = 0
    return s - math.log(d)

def arm_key(a): return f"P{a['P']}_d{a['d']}_L{a['L']}"

def coprime_frac(d):
    f, n, p = 1.0, d, 2
    while p * p <= n:
        if n % p == 0:
            f *= 1 - 1 / p
            while n % p == 0: n //= p
        p += 1
    if n > 1: f *= 1 - 1 / n
    return f

def load_state(arms):
    st = json.load(open(STATE)) if os.path.exists(STATE) else {}
    st.setdefault('arms', {})
    for a in arms:
        s = st['arms'].setdefault(arm_key(a), {})
        s.setdefault('next_m', random.randrange(10**6, 10**7) * 2 + 1)
        for k, v in dict(value=0.0, secs=0.0, logs=[], pcal=0.0, calhits=0, tested=0, completed=0,
                         hits=0, sec_per_m=None, prior=None, jobs=0, cand=0).items():
            s.setdefault(k, v)
        s['cfg'] = a
    st.setdefault('lambda', 0.0)
    return st

def save_state(st):
    with LOCK:
        tmp = STATE + '.tmp'
        json.dump(st, open(tmp, 'w'), indent=1)
        os.replace(tmp, STATE)

def price_scale(st):
    """dry-run prices ignore process overhead and use an unloaded prp timing, so they run high by a
    roughly constant factor. measure that factor on arms that have both a price and real jobs."""
    r = sorted((s['value'] / s['secs']) / s['prior'] for s in st['arms'].values()
               if s.get('prior') and s.get('secs', 0) > 600 and s.get('value', 0) > 0)
    return r[len(r) // 2] if r else 0.5

def posterior(s, scale=1.0):
    """log-normal posterior on an arm's rate (expected improvements per core-second)."""
    if s.get('prior'):
        mu0, var0 = math.log(max(s['prior'] * scale, 1e-30)), 0.6 ** 2   # dry-run price: trusted, model is calibrated
    else:
        mu0, var0 = math.log(1e-6), 4.0 ** 2
    xs = s['logs'][-40:]
    if not xs: return mu0, var0
    n, m = len(xs), sum(xs) / len(xs)
    v = max(sum((x - m) ** 2 for x in xs) / (n - 1), 0.15) if n > 1 else 0.5
    pv = 1 / (1 / var0 + n / v)
    return pv * (mu0 / var0 + n * m / v), pv

def est_rate(s, scale=1.0):
    mu, v = posterior(s, scale)
    return math.exp(mu + v / 2)

# ---------------------------------------------------------------- live status for the dashboard
LIVE = dict(workers={}, recent=[], started=time.time(), ends=None, cores=0, running=True, found_session=0)

def write_status():
    with LOCK:
        d = {k: v for k, v in LIVE.items() if not k.startswith('_')}
        d['t'] = time.time()
        d['recent'] = LIVE['recent'][-40:]
        tmp = STATUS + '.tmp'
        json.dump(d, open(tmp, 'w'))
        os.replace(tmp, STATUS)

def verify_async(expr, gap):
    def go():
        try:
            import gmpy2, re
            m, P, d, a = map(int, re.fullmatch(r'(\d+)\*(\d+)#/(\d+)-(\d+)', expr).groups())
            p = m * gmpy2.primorial(P) // d - a
            ok = gmpy2.is_bpsw_prp(p) and gmpy2.is_bpsw_prp(p + gap) and gmpy2.next_prime(p) == p + gap
            status = 'OK' if ok else 'FAILED'
        except ImportError:
            status = 'NO_GMPY2'
        except Exception as e:
            status = 'ERROR'
        with LOCK:
            with open(VERIFIED, 'a') as f:
                f.write(f"{gap}\t-\t{expr}\t{status}\n")
    threading.Thread(target=go, daemon=True).start()

# ---------------------------------------------------------------- one job = one hunt process
def run_job(st, wid, a, lam, job_secs, dry=False):
    s = st['arms'][arm_key(a)]
    SL = int(a['slf'] * lnK(a['P'], a['d']))
    if dry:
        M = max(50, int(300 / coprime_frac(a['d'])))           # ~300 candidates, sieve only
    else:
        spm = s['sec_per_m'] or 4.6 * coprime_frac(a['d']) * (a['P'] / 4001) ** 2.6
        M = max(20, int(job_secs / spm))
    with LOCK:
        m0 = s['next_m']; s['next_m'] += M
    cmd = [HUNT, str(a['P']), str(a['d']), str(m0), str(M), str(SL), a['L'], f'{lam:.6e}', str(a['mcal']), RECORDS]
    env = dict(os.environ, **({'HUNT_DRY': '1'} if dry else {}))
    w = dict(arm=arm_key(a), m0=m0, M=M, tested=0, started=time.time(), last='', dry=dry)
    with LOCK: LIVE['workers'][str(wid)] = w
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True, env=env, bufsize=1)
    LIVE.setdefault('_procs', {})[wid] = proc
    S, summ, pre_pred, pre_seen = [], None, 0.0, 0
    for line in proc.stdout:
        f = line.rstrip('\n').split('\t')
        if f[0] == 'S':
            S.append(f)
        elif f[0] == 'T':
            row = [arm_key(a)] + f[1:]
            pre_pred += float(f[17]) if len(f) > 17 else 0
            if f[5] == '1': pre_seen += float(f[9]) >= a['mcal']
            with LOCK:
                with open(GAPS, 'a') as g: g.write('\t'.join(row) + '\n')
                w['tested'] += 1
                w['last'] = f"gap {f[8]} merit {float(f[9]):.2f}" if f[5] == '1' else 'abandoned after one side'
                LIVE['recent'].append(dict(t=time.time(), arm=arm_key(a), m=int(f[1]), done=f[5] == '1',
                                           gap=int(f[8]), merit=float(f[9]), rec=float(f[10]), hit=f[15] == '1'))
                LIVE['recent'] = LIVE['recent'][-200:]
            if f[15] == '1':
                expr = f"{f[1]}*{a['P']}#/{a['d']}-{f[6]}"
                with LOCK:
                    with open(FOUND, 'a') as fo:
                        fo.write(f"{f[8]}\t{float(f[9]):.4f}\t{expr}\tprevious_record_merit={f[10]}\t{time.strftime('%Y-%m-%d %H:%M')}\n")
                    LIVE['found_session'] += 1
                print(f"\n*** RECORD: gap {f[8]}  merit {float(f[9]):.4f}  (old {f[10]})  {expr} -> FOUND.tsv, verifying ***\n", flush=True)
                verify_async(expr, int(f[8]))
        elif f[0] == '#':
            summ = dict(x.split('=', 1) for x in f[1:])
    proc.wait()
    with LOCK:
        LIVE['workers'].pop(str(wid), None)
        LIVE['_procs'].pop(wid, None)
    if not summ:
        return None
    if dry:
        over = float(summ['sieve_s']) + float(summ['score_s'])
        v = c = 0.0
        for x in S:
            cpol, vpol = float(x[4]), float(x[7])
            if vpol > 0 and vpol >= lam * cpol: v += vpol; c += cpol
        price = v / max(over + c, 1e-9)
        with LOCK:
            s['prior'] = price
        rec = dict(t=time.time(), kind='dry', arm=arm_key(a), price=price, cand=len(S))
    else:
        secs = float(summ.get('cpu_s') or summ['total_s'])
        value = float(summ['value'])
        rate = value / max(secs, 1e-9)
        with LOCK:
            s['value'] += value; s['secs'] += secs; s['jobs'] += 1
            s['logs'].append(math.log(max(rate, 1e-30)))
            s['pcal'] += pre_pred; s['calhits'] += pre_seen
            for k in ('tested', 'completed', 'hits', 'cand'): s[k] += int(summ[k])
            s['sec_per_m'] = float(summ['total_s']) / M
        rec = dict(t=time.time(), kind='job', arm=arm_key(a), M=M, lam=lam, rate=rate, value=value, secs=secs,
                   wall=float(summ['total_s']), tested=int(summ['tested']), cand=int(summ['cand']),
                   completed=int(summ['completed']), hits=int(summ['hits']), pre_pred=pre_pred, pre_seen=pre_seen,
                   overhead=float(summ['pre_s']) + float(summ['sieve_s']) + float(summ['score_s']))
    with LOCK:
        with open(JOBS, 'a') as j: j.write(json.dumps(rec) + '\n')
    return rec

def choose(st, arms):
    # 1) price every arm with a dry run first (cheap, model is calibrated)
    for a in arms:
        s = st['arms'][arm_key(a)]
        if s.get('prior') is None and not s.get('_pricing'):
            s['_pricing'] = True
            return a, True
    # 2) thompson sampling on the posterior
    sc = price_scale(st)
    def draw(a):
        mu, v = posterior(st['arms'][arm_key(a)], sc)
        return random.gauss(mu, math.sqrt(v))
    return max(arms, key=draw), False

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--hours', type=float, default=8)
    ap.add_argument('--cores', type=int, default=max(1, (os.cpu_count() or 2) - 2))
    ap.add_argument('--job-secs', type=float, default=600, help='target seconds per job (bigger = less overhead)')
    ap.add_argument('--arms', default=None, help='json file with a list of arms')
    ap.add_argument('--lam-factor', type=float, default=0.8)
    args = ap.parse_args()
    arms = json.load(open(args.arms)) if args.arms else (json.load(open(ARMS_FILE)) if os.path.exists(ARMS_FILE) else DEFAULT_ARMS)
    st = load_state(arms)
    for s in st['arms'].values(): s.pop('_pricing', None)
    if os.path.exists(STOPF): os.remove(STOPF)
    end = time.time() + args.hours * 3600
    LIVE.update(started=time.time(), ends=end, cores=args.cores, running=True, arms=[arm_key(a) for a in arms])

    def stop_requested():
        return os.path.exists(STOPF) or time.time() >= end

    def worker(wid):
        while not stop_requested():
            with LOCK:
                a, dry = choose(st, arms)
                # lambda (the stopping-rule bar). v3.0 bug: it stayed 0 until an arm had a full core-hour,
                # which silently switched OFF the one-sided skip (46% more prime tests per center).
                # now: trusted achieved rates when we have them, otherwise a deliberately low bar from
                # the dry-run prices (half the scaled best price) so the skip is on from minute one.
                sc_ = price_scale(st); real = []
                for c in arms:
                    s_ = st['arms'][arm_key(c)]
                    if s_.get('secs', 0) >= 1200 and s_.get('jobs', 0) >= 2:
                        real.append(min(s_['value'] / s_['secs'], est_rate(s_, sc_)))
                if real:
                    lam = args.lam_factor * max(real)
                else:
                    priced = [st['arms'][arm_key(c)]['prior'] for c in arms if st['arms'][arm_key(c)].get('prior')]
                    lam = 0.5 * sc_ * max(priced) if priced else 0.0
                st['lambda'] = lam
            rec = run_job(st, wid, a, lam, args.job_secs, dry=dry)
            save_state(st)
            if rec and rec['kind'] == 'job':
                print(f"[{time.strftime('%H:%M:%S')}] core {wid:>2} {rec['arm']:<20} tested {rec['tested']:>4}/{rec['cand']:<5} "
                      f"rate {rec['rate']*3600:.2e}/core-h  est {est_rate(st['arms'][rec['arm']], price_scale(st))*3600:.2e}  "
                      f"cal(m>={a['mcal']}) {rec['pre_pred']:.1f}/{rec['pre_seen']}" + (f"  *** {rec['hits']} RECORD(S)" if rec['hits'] else ''), flush=True)
            elif rec:
                print(f"[{time.strftime('%H:%M:%S')}] core {wid:>2} priced {rec['arm']:<20} model rate {rec['price']*3600:.2e} records/core-h", flush=True)
            try:
                import report; report.build()
            except Exception:
                pass

    def status_loop():
        while LIVE['running']:
            write_status()
            if os.path.exists(STOPF) and open(STOPF).read().strip() == 'now':
                for p in list(LIVE.get('_procs', {}).values()):
                    try: p.terminate()
                    except Exception: pass
            time.sleep(2)

    def on_signal(sig, frm):
        open(STOPF, 'w').write('now')
    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)

    threading.Thread(target=status_loop, daemon=True).start()
    ths = [threading.Thread(target=worker, args=(i,)) for i in range(args.cores)]
    for t in ths: t.start(); time.sleep(0.5)
    for t in ths: t.join()
    LIVE['running'] = False
    write_status()
    save_state(st)
    if os.path.exists(STOPF): os.remove(STOPF)
    print('hunt finished.', flush=True)

if __name__ == '__main__':
    main()
