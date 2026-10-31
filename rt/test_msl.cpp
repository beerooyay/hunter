// test_msl.cpp -- runs the exact GPU kernel source (rt/fermat.metal) on the CPU and checks every
// answer against GMP's powm, the definition of a base-2 Fermat test: 2^(n-1) == 1 (mod n).
//
// a SIMD group is emulated with SIMD_W real threads that meet at a barrier for every shuffle,
// broadcast, any and max, so the kernel runs with its real cross-lane data flow. the kernel is
// width-generic: build.sh runs this at widths 2, 4 and 32 (the M-series width), and the host loop
// below walks the exponent in chunks exactly the way rt/hunter_metal.m does.
// what this can't check is Apple's compiler accepting the file: `./hunter bench` on a Mac does that.
#include <atomic>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <thread>
#include <vector>
#include <gmp.h>
typedef uint32_t uint;
typedef uint64_t ulong;
typedef uint8_t uchar;
typedef uint16_t ushort;
#define kernel
#define device
#define constant


// ---- one emulated SIMD group
struct Bar {
    std::atomic<int> count{0}, gen{0};
    int n = 1;
    void wait() {
        int g = gen.load();
        if (count.fetch_add(1) == n - 1) { count.store(0); gen.fetch_add(1); }
        else while (gen.load() == g) std::this_thread::yield();
    }
};
static Bar g_bar;
static ulong g_ex[2][64];
static thread_local int t_cur = 0, t_lane = 0;
static ulong xchg(ulong v, int src) {
    g_ex[t_cur][t_lane] = v;
    g_bar.wait();
    ulong r = g_ex[t_cur][src];
    t_cur ^= 1;
    return r;
}
static uint simd_broadcast(uint v, ushort l) { return (uint)xchg(v, l); }
static uint simd_shuffle_down(uint v, ushort d) { int s = t_lane + d; return (uint)xchg(v, s < SIMD_W ? s : t_lane); }
static uint simd_shuffle_up(uint v, ushort d) { int s = t_lane - (int)d; return (uint)xchg(v, s >= 0 ? s : t_lane); }
static bool simd_any(bool b) {
    g_ex[t_cur][t_lane] = b;
    g_bar.wait();
    bool r = false;
    for (int i = 0; i < SIMD_W; i++) r = r || g_ex[t_cur][i];
    t_cur ^= 1;
    return r;
}
static uint simd_max(uint v) {
    g_ex[t_cur][t_lane] = v;
    g_bar.wait();
    uint r = 0;
    for (int i = 0; i < SIMD_W; i++) if ((uint)g_ex[t_cur][i] > r) r = (uint)g_ex[t_cur][i];
    t_cur ^= 1;
    return r;
}
static inline uint mulhi(uint a, uint b) { return (uint)(((ulong)a * b) >> 32); }
static inline uint max(uint a, uint b) { return a > b ? a : b; }

#include "fermat_cpu.h"   // rt/fermat.metal with the [[attributes]] stripped

typedef void (*KFN)(const uint *, uint *, uchar *, uint &, uint &, int &, int &, uint, uint);
static KFN kernel_for(int K) {
    switch (K) {
#define C(KK) case KK: return fermat_simd_##KK;
        C(1) C(2) C(3) C(4) C(5) C(6) C(7) C(8) C(9) C(10) C(11) C(12)
        C(13) C(14) C(15) C(16) C(17) C(18) C(19) C(20) C(21) C(22) C(23) C(24)
#undef C
    }
    return nullptr;
}

// the same chunked walk as the Metal host: x starts at R mod n, then bits from the top, then bs = -1
static int run_one(const uint *n, const uint *rm, uint nl, int chunk) {
    int K = (int)((nl + 2 + SIMD_W - 1) / SIMD_W);
    KFN f = kernel_for(K);
    if (!f) { fprintf(stderr, "no kernel for K=%d\n", K); return -1; }
    std::vector<uint> N(n, n + nl), X(rm, rm + nl);
    uchar out = 0;
    int top = (int)nl * 32 - 1;
    while (top > 0 && !((N[top >> 5] >> (top & 31)) & 1)) top--;
    g_bar.n = SIMD_W; g_bar.count = 0;
    std::vector<std::thread> th;
    for (int lane = 0; lane < SIMD_W; lane++) {
        th.emplace_back([&, lane]() {
            t_lane = lane; t_cur = 0;
            uint unl = nl, ucnt = 1;
            for (int bs = top; ; ) {
                int b = bs < 0 ? -1 : bs, c = bs < 0 ? 0 : chunk;
                f(N.data(), X.data(), &out, unl, ucnt, b, c, (uint)lane, (uint)lane);
                g_bar.wait();                         // dispatch boundary
                if (bs < 0) break;
                bs -= c;
                if (bs < 0) bs = -1;
            }
        });
    }
    for (auto &x : th) x.join();
    return out;
}

static void pack(mpz_t z, uint nl, std::vector<uint> &dn, std::vector<uint> &dr) {
    dn.assign(nl, 0); dr.assign(nl, 0);
    size_t c;
    mpz_export(dn.data(), &c, -1, 4, 0, 0, z);
    mpz_t R; mpz_init(R); mpz_setbit(R, (mp_bitcnt_t)nl * 32); mpz_mod(R, R, z);
    mpz_export(dr.data(), &c, -1, 4, 0, 0, R); mpz_clear(R);
}

int main(int argc, char **argv) {
    int big = argc > 1 ? atoi(argv[1]) : 0;          // also run this many 1,706-digit numbers
    int total = 0, bad = 0, pos = 0;
    mpz_t n, r, two, K, sp, g;
    mpz_inits(n, r, two, K, sp, g, NULL);
    mpz_set_ui(two, 2);
    mpz_primorial_ui(sp, 3000);
    std::vector<uint> dn, dr;
    auto check = [&](mpz_t z, uint nl, int chunk) {
        pack(z, nl, dn, dr);
        int got = run_one(dn.data(), dr.data(), nl, chunk);
        mpz_sub_ui(r, z, 1); mpz_powm(r, two, r, z);
        int want = mpz_cmp_ui(r, 1) == 0;
        total++; pos += want;
        if (got != want) { bad++; gmp_fprintf(stderr, "MISMATCH nl=%u chunk=%d got %d want %d n=%Zd\n", nl, chunk, got, want, z); }
    };
    // 1) small edge cases incl. base-2 pseudoprimes (341, 561, ...), padded with zero limbs
    const unsigned long small[] = {3, 5, 7, 9, 15, 341, 561, 645, 1105, 1387, 1729, 1905, 2047, 2465,
                                   65537, 2147483647UL, 4294967279UL, 4294967291UL, 4294967295UL};
    for (unsigned long v : small)
        for (uint nl : {1u, 2u, 3u}) { mpz_set_ui(n, v); check(n, nl, nl == 2 ? 5 : 64); }
    // 2) multi-limb: primes and survivor-like composites at sizes that cross block boundaries
    for (unsigned P : {61u, 127u, 223u, 401u, 1009u}) {
        mpz_primorial_ui(K, P); mpz_divexact_ui(K, K, 30); mpz_mul_ui(K, K, 1000003);
        uint nl = (uint)(mpz_sizeinbase(K, 2) / 32) + 1;
        int cnt = 0;
        for (unsigned long off = 2; cnt < 4; off += 2) {
            mpz_add_ui(n, K, off); mpz_gcd(g, n, sp);
            if (mpz_cmp_ui(g, 1) == 0) { check(n, nl, 7 + cnt * 40); cnt++; }
        }
        mpz_nextprime(n, K); check(n, nl, 33);          // a real prime
        mpz_add_ui(n, K, 1); if (mpz_even_p(n)) mpz_add_ui(n, n, 1);
        check(n, nl, 1000);                             // one big chunk
    }
    // 3) optionally the real size: 4001#/210 (179 limbs)
    if (big > 0) {
        mpz_primorial_ui(K, 4001); mpz_divexact_ui(K, K, 210); mpz_mul_ui(K, K, 1000003);
        uint nl = (uint)(mpz_sizeinbase(K, 2) / 32) + 2;
        mpz_nextprime(n, K); check(n, nl, 512);
        for (int i = 1; i < big; i++) { mpz_add_ui(n, K, 2 * i + 2); check(n, nl, 512); }
    }
    printf("gpu kernel (simd width %d, emulated on cpu): %d numbers, %d probable primes, %d mismatches vs gmp powm\n",
           SIMD_W, total, pos, bad);
    return bad ? 1 : 0;
}
