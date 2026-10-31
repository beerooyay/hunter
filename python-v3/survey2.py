import subprocess, os, sys, math, json
import gmpy2
def survey(P, d, lam, ncand=260, L='1e9', slf=25, m0=7000001):
    lnK = float(gmpy2.log(gmpy2.primorial(P) // d)); SL = int(slf * lnK)
    phi = 1
    for p in [2,3,5,7,11,13,17,19,23,29,31]:
        if d % p == 0: phi *= (1 - 1/p)
    M = int(ncand / phi)
    out = subprocess.run(['./hunt', str(P), str(d), str(m0), str(M), str(SL), L, f'{lam:.6e}', '15', 'records.txt'],
                         capture_output=True, text=True, env=dict(os.environ, HUNT_DRY='1')).stdout.splitlines()
    S = [l.split('\t') for l in out if l[0] == 'S']
    kv = dict(x.split('=', 1) for x in [l for l in out if l[0] == '#'][0].split('\t')[1:])
    over = float(kv['sieve_s']) + float(kv['score_s'])            # pre_s amortizes away in long batches
    v = c = 0; nt = 0
    for x in S:
        sc, cpol, vpol = float(x[2]), float(x[4]), float(x[7])
        if vpol >= lam * cpol and vpol > 0: v += vpol; c += cpol; nt += 1
    return dict(P=P, d=d, digits=round(lnK / 2.302585), cand=len(S), tested=nt, t_prp=float(kv['t_prp']),
                over_per_cand=over / len(S), rate_hr=3600 * v / (over + c), score_sum=sum(float(x[2]) for x in S))
if __name__ == '__main__':
    P, d = int(sys.argv[1]), int(sys.argv[2]); lam = float(sys.argv[3]) if len(sys.argv) > 3 else 3e-5
    print(json.dumps(survey(P, d, lam)), flush=True)
