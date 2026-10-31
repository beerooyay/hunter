// hunt.c -- rb labs prime gap hunter, core engine (v2)
//
// centers N = m * (P#/d), m in [m0, m0+M), gcd(m,d) = 1.
//
// 1. combined sieve over all m at once. small primes: direct striding. large primes: a euclid-style
//    modular search jumps straight to the m values whose window contains a multiple of p, so a prime
//    costs O(log p) per hit instead of O(M). this is what makes deep sieves (1e9+) affordable.
// 2. score: a survivor is prime with probability q = 1/(ln N * prod_{p<=L}(1-1/p)) (mertens; checked
//    against real primes, see README). from the survivor pattern we get the exact model probability
//    that the gap straddling N beats the current record merit for its size (records.txt).
// 3. staged test with the refinement-frontier stopping rule: a candidate is worth testing iff
//        score >= lambda * expected_cost
//    where lambda is the improvement rate the learner believes it can already get elsewhere.
//    after the next prime is found the score is recomputed; the left side is searched only if the
//    conditional score still clears lambda * remaining_cost.
//
// build: cc -O3 -march=native -o hunt hunt.c -lgmp -lm
//        (mac/homebrew: cc -O3 -mcpu=native -I/opt/homebrew/include -L/opt/homebrew/lib -o hunt hunt.c -lgmp -lm)
// usage: ./hunt P d m0 M SL L lambda mcal records.txt
// output: tsv lines 'T ...' for tested candidates, one '#' summary line.

#include <gmp.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

typedef unsigned __int128 u128;

static double now(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec + 1e-9 * t.tv_nsec;
}

static uint64_t *primes_upto(uint64_t L, size_t *n) {
    // segmented sieve of eratosthenes (odd only) so L can be 1e9+ without a giant array
    uint64_t r = (uint64_t)sqrt((double)L) + 1;
    uint8_t *s = calloc(r + 1, 1);
    size_t cap = (size_t)(L / (log((double)L) - 1.1)) + 1000, k = 0;
    uint64_t *out = malloc(cap * sizeof(uint64_t));
    uint64_t *base = malloc((r + 1) * sizeof(uint64_t));
    size_t nb = 0;
    for (uint64_t i = 2; i <= r; i++)
        if (!s[i]) { base[nb++] = i; for (uint64_t j = i * i; j <= r; j += i) s[j] = 1; }
    free(s);
    const uint64_t SEG = 1 << 22;
    uint8_t *seg = malloc(SEG);
    for (uint64_t lo = 2; lo <= L; lo += SEG) {
        uint64_t hi = lo + SEG - 1; if (hi > L) hi = L;
        memset(seg, 0, hi - lo + 1);
        for (size_t i = 0; i < nb; i++) {
            uint64_t p = base[i];
            if (p * p > hi) break;
            uint64_t st = (lo + p - 1) / p * p; if (st < p * p) st = p * p;
            for (uint64_t j = st; j <= hi; j += p) seg[j - lo] = 1;
        }
        for (uint64_t j = lo; j <= hi; j++) if (!seg[j - lo]) { if (k == cap) { cap *= 2; out = realloc(out, cap * 8); } out[k++] = j; }
    }
    free(seg); free(base);
    *n = k;
    return out;
}

static uint64_t gcd64(uint64_t a, uint64_t b) { while (b) { uint64_t t = a % b; a = b; b = t; } return a; }

// smallest x >= 0 with l <= (a*x) mod m <= r  (0 <= l <= r < m). -1 if none. verified against brute force.
static int64_t msearch(uint64_t a, uint64_t m, uint64_t l, uint64_t r) {
    if (l == 0) return 0;
    a %= m;
    if (a == 0) return -1;
    uint64_t k = (l + a - 1) / a;
    if ((u128)a * k <= r) return (int64_t)k;
    uint64_t nl = (a - r % a) % a, nr = (a - l % a) % a;
    int64_t y = (nl <= nr) ? msearch(m % a, a, nl, nr) : 0;
    if (y < 0) return -1;
    for (;; y++) {
        u128 x = ((u128)m * y + l + a - 1) / a;
        if ((u128)a * x <= (u128)m * y + r) return (int64_t)x;
        if (y > (int64_t)a) return -1;
    }
}

static float *rec;
static long rec_max;
static inline int improves(long g, double lnN) {
    double rm = (g <= rec_max) ? rec[g] : 0.0;
    return g / lnN > rm;
}

#define BIT(b, i) ((b)[(i) >> 6] >> ((i)&63) & 1)
#define SET(b, i) ((b)[(i) >> 6] |= 1ULL << ((i)&63))

int main(int argc, char **argv) {
    if (argc < 10) { fprintf(stderr, "usage: %s P d m0 M SL L lambda mcal records.txt\n", argv[0]); return 1; }
    uint32_t P = atoi(argv[1]);
    uint64_t d = strtoull(argv[2], 0, 10), m0 = strtoull(argv[3], 0, 10);
    long M = atol(argv[4]);
    long SL = atol(argv[5]);
    uint64_t L = (uint64_t)atof(argv[6]);
    double lambda = atof(argv[7]), mcal = atof(argv[8]);
    {
        FILE *f = fopen(argv[9], "r");
        if (!f) { perror("records"); return 1; }
        long g; double m; rec_max = 0;
        while (fscanf(f, "%ld %lf", &g, &m) == 2) if (g > rec_max) rec_max = g;
        rewind(f); rec = calloc(rec_max + 1, sizeof(float));
        while (fscanf(f, "%ld %lf", &g, &m) == 2) rec[g] = (float)m;
        fclose(f);
    }
    double t0 = now();
    size_t np; uint32_t *pr;
    { uint64_t *p64 = primes_upto(L, &np); pr = malloc(np * sizeof(uint32_t)); for (size_t i = 0; i < np; i++) pr[i] = (uint32_t)p64[i]; free(p64); }
    if (L > 4000000000ULL) { fprintf(stderr, "L must be <= 4e9\n"); return 1; }
    mpz_t K, N, t; mpz_inits(K, N, t, NULL);
    mpz_primorial_ui(K, P);
    if (!mpz_divisible_ui_p(K, d)) { fprintf(stderr, "d must divide P#\n"); return 1; }
    mpz_divexact_ui(K, K, d);
    long e2; double mant = mpz_get_d_2exp(&e2, K);
    double lnK = log(mant) + e2 * log(2.0);
    double lprod = 0; for (size_t i = 0; i < np; i++) lprod += log1p(-1.0 / pr[i]);
    uint32_t *kr = malloc(np * sizeof(uint32_t));
    for (size_t i = 0; i < np; i++) kr[i] = mpz_fdiv_ui(K, pr[i]);
    double t_pre = now() - t0;

    // PRP cost calibration (a few tests on numbers of this size)
    double t_prp;
    {   // time PRP tests on numbers of this size that have no small factor (so trial division can't short-circuit)
        volatile int sink = 0; mpz_t g, sp; mpz_inits(g, sp, NULL); mpz_primorial_ui(sp, 2000);
        mpz_mul_ui(t, K, m0); mpz_add_ui(t, t, 1); if (mpz_even_p(t)) mpz_add_ui(t, t, 1); int done = 0; double a = now();
        while (done < 3) { mpz_gcd(g, t, sp); if (mpz_cmp_ui(g, 1) == 0) { sink += mpz_probab_prime_p(t, 1); done++; } mpz_add_ui(t, t, 2); }
        t_prp = (now() - a) / 3; (void)sink; mpz_clears(g, sp, NULL);
    }

    // block size so the block bitset stays ~64MB
    double msk = getenv("HUNT_MSK") ? atof(getenv("HUNT_MSK")) : 3.0;
    size_t words = (size_t)(SL + 64) / 64 + 1;
    long MB = (long)(64e6 / (2.0 * words * 8)); if (MB < 1) MB = 1; if (MB > M) MB = M;
    uint64_t *bits = malloc((size_t)MB * 2 * words * 8);
    long *R = malloc((SL + 1) * sizeof(long)), *Lf = malloc((SL + 1) * sizeof(long));
    long *cntL = malloc((SL + 2) * sizeof(long));

    long ncand = 0, ntested = 0, ncomplete = 0, nhits = 0;
    double sum_score = 0, value = 0, sum_pcal = 0, calhits = 0, t_sieve = 0, t_score = 0, t_test = 0;
    double prp_n = 0, prp_t = 0;

    for (long b0 = 0; b0 < M; b0 += MB) {
        long mb = (M - b0 < MB) ? M - b0 : MB;
        uint64_t mstart = m0 + b0;
        double ts = now();
        memset(bits, 0, (size_t)mb * 2 * words * 8);
        for (size_t i = 0; i < np; i++) {
            uint64_t p = pr[i], a = kr[i];
            double hits = (double)mb * (2.0 * SL + 1) / p;
            if (p <= (uint64_t)(2 * SL + 1) || msk * (hits + 1) >= mb) {
                uint64_t mr = mstart % p;
                for (long k = 0; k < mb; k++, mr = (mr + 1 == p) ? 0 : mr + 1) {
                    uint64_t r = (uint64_t)(((u128)mr * a) % p);
                    uint64_t *rt = bits + (size_t)k * 2 * words, *lf = rt + words;
                    uint64_t s = (p - r) % p; if (s == 0) s = p;
                    for (uint64_t o = s; o <= (uint64_t)SL; o += p) SET(rt, o);
                    s = r; if (s == 0) s = p;
                    for (uint64_t o = s; o <= (uint64_t)SL; o += p) SET(lf, o);
                }
            } else {
                // r_k = (B + a*k) mod p must land in [p-SL, p-1] u [0, SL]  ->  a*k mod p in [lo, lo+2SL] (mod p)
                uint64_t B = (uint64_t)(((u128)(mstart % p) * a) % p);
                long k = 0;
                while (k < mb) {
                    uint64_t Bk = (uint64_t)((B + (u128)a * k) % p);
                    uint64_t lo = (p - SL % p + p - Bk) % p, hi = (lo + 2 * SL) % p;
                    int64_t x;
                    if (lo <= hi) x = msearch(a, p, lo, hi);
                    else { int64_t x1 = msearch(a, p, lo, p - 1), x2 = msearch(a, p, 0, hi); x = (x1 < 0) ? x2 : (x2 < 0 ? x1 : (x1 < x2 ? x1 : x2)); }
                    if (x < 0) break;
                    k += x;
                    if (k >= mb) break;
                    uint64_t r = (uint64_t)((B + (u128)a * k) % p);
                    uint64_t *rt = bits + (size_t)k * 2 * words, *lf = rt + words;
                    if (r == 0) { if ((long)p <= SL) { SET(rt, p); SET(lf, p); } }
                    else if (r >= p - SL) SET(rt, p - r);
                    else if (r <= (uint64_t)SL) SET(lf, r);
                    k++;
                }
            }
        }
        t_sieve += now() - ts;

        for (long k = 0; k < mb; k++) {
            uint64_t m = mstart + k;
            if (gcd64(m, d) != 1) continue;
            ncand++;
            double t1 = now();
            uint64_t *rt = bits + (size_t)k * 2 * words, *lf = rt + words;
            long nR = 0, nL = 0;
            for (long o = 1; o <= SL; o++) { if (!BIT(rt, o)) R[nR++] = o; if (!BIT(lf, o)) Lf[nL++] = o; }
            double lnN = log((double)m) + lnK;
            double q = 1.0 / (lnN * exp(lprod)), lq = log1p(-q);
            // smallest gap that could improve the table at this ln N
            long G0 = 2; while (G0 < 2 * SL && !improves(G0, lnN)) G0 += 2;
            // cntL[x] = number of left survivors with offset < x
            { long j = 0; for (long x = 0; x <= SL + 1; x++) { while (j < nL && Lf[j] < x) j++; cntL[x] = j; } }
            // cheap upper bound s0 = P(gap >= G0)
            double s0 = 0, w = q;
            for (long i = 0; i < nR; i++, w *= (1 - q)) {
                long need = G0 - R[i];
                double tail = (need <= 1) ? 1.0 : (need > SL + 1 ? exp(nL * lq) : exp(cntL[need] * lq));
                s0 += w * tail;
                if (w < 1e-30) break;
            }
            // pre-test probability of merit >= mcal (for calibrating the tail of the model)
            double scal0 = 0; { long Gc = (long)ceil(mcal * lnN); double w2 = q;
                for (long i = 0; i < nR; i++, w2 *= (1 - q)) { long need = Gc - R[i];
                    double tail = (need <= 1) ? 1.0 : (need > SL + 1 ? exp(nL * lq) : exp(cntL[need] * lq));
                    scal0 += w2 * tail; if (w2 < 1e-30) break; } }
            double eR = (1 - exp(nR * lq)) / q, eL = (1 - exp(nL * lq)) / q;  // expected PRP tests per side
            double tp = (prp_n > 40) ? prp_t / prp_n : t_prp;                   // measured cost of one PRP test
            double sc = 0, vpol = 0, pcont = 0;
            int dry = getenv("HUNT_DRY") != NULL;
            // cheap filter: even with zero left-side cost the candidate must clear lambda * right-side cost
            if (dry || s0 >= lambda * eR * tp) {
                // exact score: sum over (right, left) first-prime pairs that beat the table.
                // inner = P(improve | next prime at R[i]); the left side is only searched when
                // inner >= lambda * eL * tp, so we also get the value and cost of that exact policy.
                double wr = q, lthr = lambda * eL * tp;
                for (long i = 0; i < nR; i++, wr *= (1 - q)) {
                    if (wr < s0 * 1e-9) break;
                    long need = G0 - R[i]; long j0 = (need <= 1) ? 0 : (need > SL + 1 ? nL : cntL[need]);
                    double wl = q * exp(j0 * lq), inner = 0;
                    for (long j = j0; j < nL; j++, wl *= (1 - q)) {
                        if (wr * wl < s0 * 1e-12) break;
                        if (improves(R[i] + Lf[j], lnN)) inner += wl;
                    }
                    inner += exp(nL * lq);  // no left prime inside the window: a gap > SL, record-class
                    sc += wr * inner;
                    if (inner >= lthr) { vpol += wr * inner; pcont += wr; }
                }
            }
            double cpol = tp * (eR + pcont * eL);   // expected seconds of PRP work under the policy
            sum_score += sc;
            t_score += now() - t1;
            if (dry) { printf("S\t%llu\t%.6e\t%.6e\t%.4f\t%ld\t%ld\t%.6e\t%.4f\t%.6e\n", (unsigned long long)m, sc, s0, cpol, nR, nL, vpol, pcont, q); continue; }
            if (!(vpol >= lambda * cpol) || vpol <= 0) continue;

            double t2 = now();
            ntested++;
            mpz_mul_ui(N, K, m);
            long b = -1, a = -1; int tr = 0, tl = 0;
            for (long i = 0; i < nR; i++) {
                mpz_add_ui(t, N, R[i]); tr++;
                if (mpz_probab_prime_p(t, 1)) { b = R[i]; break; }
            }
            double scb = 0, pcal = 0; int completed = 0;
            if (b >= 0) {
                double wl = q;
                for (long j = 0; j < nL; j++, wl *= (1 - q)) {
                    if (wl < 1e-14) break;
                    long g = b + Lf[j];
                    if (improves(g, lnN)) scb += wl;
                    if (g / lnN >= mcal) pcal += wl;
                }
                scb += exp(nL * lq); pcal += exp(nL * lq);
                if (scb >= lambda * eL * ((prp_n > 40) ? prp_t / prp_n : t_prp)) {
                    for (long j = 0; j < nL; j++) {
                        mpz_sub_ui(t, N, Lf[j]); tl++;
                        if (mpz_probab_prime_p(t, 1)) { a = Lf[j]; break; }
                    }
                    if (a >= 0) completed = 1;
                }
            }
            double dt = now() - t2;
            t_test += dt; prp_n += tr + tl; prp_t += dt;
            long gap = completed ? a + b : 0;
            double merit = completed ? gap / lnN : 0, rm = (completed && gap <= rec_max) ? rec[gap] : 0;
            int hitcal = completed && merit >= mcal, hit = 0;
            if (completed) {
                ncomplete++; value += scb; sum_pcal += pcal; calhits += hitcal;
                if (merit > rm) {
                    mpz_add_ui(t, N, b); int ok1 = mpz_probab_prime_p(t, 25) > 0;
                    mpz_sub_ui(t, N, a); int ok2 = mpz_probab_prime_p(t, 25) > 0;
                    if (ok1 && ok2) { hit = 1; nhits++; }
                }
            }
            printf("T\t%llu\t%d\t%.4e\t%.4e\t%d\t%ld\t%ld\t%ld\t%.4f\t%.4f\t%d\t%d\t%.5f\t%d\t%d\t%.3f\t%.6e\t%.6e\t%.6e\t%.3f\n",
                   (unsigned long long)m, (int)(lnN / log(10.0)) + 1, sc, scb, completed, a, b, gap, merit, rm,
                   tr, tl, pcal, hitcal, hit, dt, scal0, q, vpol, cpol);
            fflush(stdout);
        }
    }
    double tt = now() - t0;
    double cpu = (double)clock() / CLOCKS_PER_SEC;
    printf("#\tP=%u\td=%llu\tm0=%llu\tM=%ld\tSL=%ld\tL=%llu\tlambda=%.4e\tcand=%ld\ttested=%ld\tcompleted=%ld\tsum_score=%.6e"
           "\tvalue=%.6e\tpcal=%.4f\tcalhits=%.0f\thits=%ld\tt_prp=%.5f\tprp_mean=%.5f\tpre_s=%.2f\tsieve_s=%.2f\tscore_s=%.2f\ttest_s=%.2f\ttotal_s=%.2f\tcpu_s=%.2f\n",
           P, (unsigned long long)d, (unsigned long long)m0, M, SL, (unsigned long long)L, lambda, ncand, ntested, ncomplete,
           sum_score, value, sum_pcal, calhits, nhits, t_prp, prp_n ? prp_t / prp_n : 0, t_pre, t_sieve, t_score, t_test, tt, cpu);
    return 0;
}
