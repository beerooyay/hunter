// test_msl.cpp -- runs the exact Metal kernel source (rt/fermat.metal) on the CPU and checks every
// answer against GMP's powm, i.e. the definition of a base-2 Fermat test: 2^(n-1) == 1 (mod n).
// it validates the kernel's math and macros on any machine; what it can't check is Apple's
// Metal compiler accepting the file -- `./hunter bench` on a Mac does that.
//   build: see `./build.sh test`
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <vector>
#include <gmp.h>
typedef uint32_t uint;
typedef uint64_t ulong;
typedef uint8_t uchar;
#define kernel
#define device
#define constant
#define threadgroup
#include "fermat_cpu.h"   // rt/fermat.metal with the [[attributes]] stripped

static int pack(mpz_t n, uint *dn, uint *dr, int nl) {
    if (mpz_sizeinbase(n, 2) > (size_t)nl * 32) return 0;
    memset(dn, 0, 4 * nl); memset(dr, 0, 4 * nl);
    size_t c; mpz_export(dn, &c, -1, 4, 0, 0, n);
    mpz_t R; mpz_init(R); mpz_setbit(R, (mp_bitcnt_t)nl * 32); mpz_mod(R, R, n);
    mpz_export(dr, &c, -1, 4, 0, 0, R); mpz_clear(R);
    return 1;
}

int main() {

    int total = 0, bad = 0, pos = 0;
    mpz_t n, two, r, K, sp, g; mpz_inits(n, two, r, K, sp, g, NULL); mpz_set_ui(two, 2);
    mpz_primorial_ui(sp, 3000);
    auto batch = [&](std::vector<mpz_t*> &xs, int nl) {
        int cnt = (int)xs.size();
        std::vector<uint> N(cnt * nl), RM(cnt * nl), AN(nl), AR(nl), XS(cnt * nl), TS(cnt * (nl + 2));
        std::vector<uchar> o1(cnt), o2(cnt);
        for (int i = 0; i < cnt; i++) {                 // the host does array-of-structs -> struct-of-arrays
            pack(*xs[i], AN.data(), AR.data(), nl);
            for (int j = 0; j < nl; j++) { N[j * cnt + i] = AN[j]; RM[j * cnt + i] = AR[j]; }
        }
        uint unl = nl, ucnt = cnt;
        for (uint gid = 0; gid < (uint)cnt; gid++) fermat_dev(N.data(), RM.data(), XS.data(), TS.data(), o1.data(), unl, ucnt, gid);
        const uint tg = 8;
        std::vector<uint> sh(tg * (2 * nl + 2));
        for (uint gid = 0; gid < (uint)cnt; gid++) fermat_tg(N.data(), RM.data(), o2.data(), unl, ucnt, sh.data(), gid, gid % tg);
        for (int i = 0; i < cnt; i++) {
            mpz_sub_ui(r, *xs[i], 1); mpz_powm(r, two, r, *xs[i]);
            int want = mpz_cmp_ui(r, 1) == 0;
            total += 2; pos += want;
            if (o1[i] != want) bad++;
            if (o2[i] != want) bad++;
        }
    };
    // 1) one-limb edge cases, including base-2 pseudoprimes that a Fermat test must call "probable prime"
    {
        unsigned long v[] = {3, 5, 7, 9, 15, 341, 561, 645, 1105, 1387, 1729, 1905, 2047, 2465, 4294967291UL, 4294967279UL, 4294967295UL, 65537, 2147483647UL};
        std::vector<mpz_t*> xs; static mpz_t s[32];
        for (int i = 0; i < 19; i++) { mpz_init_set_ui(s[i], v[i]); xs.push_back(&s[i]); }
        batch(xs, 1);
        std::vector<mpz_t*> xs2; for (int i = 0; i < 19; i++) xs2.push_back(&s[i]);
        batch(xs2, 3);                                    // same numbers with leading zero limbs
    }
    // 2) survivor-like numbers m*P#/210 + off at 422 and 1706 digits, plus real primes found by nextprime
    unsigned Ps[2] = {1009, 4001};
    for (int k = 0; k < 2; k++) {
        mpz_primorial_ui(K, Ps[k]); mpz_divexact_ui(K, K, 210); mpz_mul_ui(K, K, 1000003);
        int nl = (int)(mpz_sizeinbase(K, 2) / 32) + 2;
        static mpz_t s[80];
        std::vector<mpz_t*> xs;
        int got = 0;
        for (unsigned long off = 2; got < (k ? 24 : 60); off += 2) {
            mpz_add_ui(n, K, off); mpz_gcd(g, n, sp);
            if (mpz_cmp_ui(g, 1) == 0) { mpz_init_set(s[got], n); xs.push_back(&s[got]); got++; }
        }
        for (int q = 0; q < (k ? 2 : 6); q++) {           // real primes
            mpz_init(s[got]); mpz_nextprime(s[got], q ? *xs.back() : K); xs.push_back(&s[got]); got++;
        }
        batch(xs, nl);
        printf("  %4u#/210: %d numbers, %d limbs\n", Ps[k], got, nl);
    }
    printf("msl kernels on cpu: %d answers (both kernels), %d probable primes, %d mismatches vs gmp powm\n", total, pos, bad);
    return bad ? 1 : 0;
}
