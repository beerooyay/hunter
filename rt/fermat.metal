// fermat.metal -- the Apple GPU kernel: batched base-2 Fermat tests, 2^(n-1) == 1 (mod n).
//
// one SIMD group (SIMD_W = 32 lanes) cooperates on each number and keeps it in registers. lane L
// owns limb positions p = L + SIMD_W*k, k < K, so a 1,706-digit number (179 limbs) is 6 limbs per
// lane. Montgomery multiplication (CIOS, R = 2^(32*nl)) runs with carry-save accumulators: every
// partial product's low half is added at its position and its high half is parked in g[] for the
// next position, which becomes the same lane after the one-limb shift; on the shift only the low
// 32 bits of each accumulator move lanes. carries are resolved once per multiplication. all
// cross-lane traffic is 32-bit simd_broadcast / simd_shuffle_up / simd_shuffle_down.
//
// the host walks the exponent in short chunks (one dispatch each, tens of milliseconds) with the
// running value kept in XS between dispatches, so no command buffer ever runs long enough to stall
// the display or trip the GPU watchdog. bs = -1 is the final step: leave the Montgomery domain and
// compare with 1.
//
// rt/test_msl.cpp compiles this exact file as C++ with emulated SIMD groups (widths 2, 4 and 32)
// and checks it against GMP; build.sh embeds it into the binary; Metal compiles it at runtime.
#include <metal_stdlib>
using namespace metal;

#ifndef SIMD_W
#define SIMD_W 32
#endif

// carry-propagate t[] into canonical 32-bit limbs (uses g[] as scratch). rounds repeat until no
// lane has a carry left; normally 2-3 rounds.
#define NORMALIZE {                                                                         \
    bool more_ = true;                                                                      \
    while (more_) {                                                                         \
        bool any_ = false;                                                                  \
        for (int k = 0; k < K; k++) { g[k] = t[k] >> 32; t[k] &= 0xfffffffful; any_ = any_ || g[k] != 0ul; } \
        for (int k = 0; k < K; k++) {   /* carries are < 2^32: 32-bit shuffles suffice */  \
            uint up_ = simd_shuffle_up((uint)g[k], (ushort)1);                              \
            uint wr_ = simd_broadcast((uint)g[k > 0 ? k - 1 : 0], (ushort)(SIMD_W - 1));    \
            t[k] += (ulong)((lane == 0u) ? (k > 0 ? wr_ : 0u) : up_);                       \
        }                                                                                   \
        more_ = simd_any(any_);                                                             \
    }                                                                                       \
    for (int k = 0; k < K; k++) g[k] = 0ul;                                                 \
}

// t is canonical and < 2n: subtract n once if t >= n
#define COND_SUB {                                                                          \
    uint hi_ = 0u;                                                                          \
    for (int k = 0; k < K; k++) {                                                           \
        uint p_ = lane + SIMD_W * k;                                                        \
        if ((uint)t[k] != nn[k]) hi_ = max(hi_, p_ + 1u);                                   \
    }                                                                                       \
    uint top_ = simd_max(hi_);                                                              \
    bool ge_ = true;                                                                        \
    if (top_ > 0u) {                                                                        \
        uint q_ = top_ - 1u;                                                                \
        uint mine_ = 0u;                                                                    \
        for (int k = 0; k < K; k++) if (lane + SIMD_W * k == q_) mine_ = ((uint)t[k] > nn[k]) ? 1u : 0u; \
        ge_ = simd_broadcast(mine_, (ushort)(q_ % SIMD_W)) != 0u;                           \
    }                                                                                       \
    if (ge_) {                                                                              \
        for (int k = 0; k < K; k++) {                                                       \
            uint p_ = lane + SIMD_W * k;                                                    \
            t[k] = (p_ <= nl) ? (t[k] + (ulong)(~nn[k]) + (p_ == 0u ? 1ul : 0ul)) : 0ul;    \
        }                                                                                   \
        NORMALIZE                                                                           \
        for (int k = 0; k < K; k++) if (lane + SIMD_W * k >= nl) t[k] = 0ul;                \
    }                                                                                       \
}

// x = x * B * R^-1 mod n with B = x (BONE = 0, a squaring) or B = 1 (BONE = 1)
#define MONT(BONE) {                                                                        \
    for (int k = 0; k < K; k++) { t[k] = 0ul; g[k] = 0ul; }                                 \
    for (int kb = 0; kb < K; kb++) {                                                        \
        for (uint l = 0u; l < (uint)SIMD_W; l++) {                                          \
            uint i = (uint)kb * SIMD_W + l;                                                 \
            if (i >= nl) break;                                                             \
            uint ai = simd_broadcast(x[kb], (ushort)l);                                     \
            for (int k = 0; k < K; k++) {                                                   \
                uint bk = (BONE) ? ((lane + SIMD_W * k) == 0u ? 1u : 0u) : x[k];            \
                t[k] += (ulong)(ai * bk);                                                   \
                g[k] += (ulong)mulhi(ai, bk);                                               \
            }                                                                               \
            uint m = simd_broadcast((uint)t[0], (ushort)0) * ninv;                          \
            for (int k = 0; k < K; k++) {                                                   \
                t[k] += (ulong)(m * nn[k]);                                                 \
                g[k] += (ulong)mulhi(m, nn[k]);                                             \
            }                                                                               \
            /* shift down one limb. the low half of position p+1 moves to lane p; the high  \
               half of position p already belongs to the new position p, on this lane */    \
            for (int k = 0; k < K; k++) {                                                   \
                uint dn_ = simd_shuffle_down((uint)t[k], (ushort)1);                        \
                uint wr_ = simd_broadcast((uint)t[k + 1 < K ? k + 1 : k], (ushort)0);       \
                uint lo_ = (lane == (uint)(SIMD_W - 1)) ? (k + 1 < K ? wr_ : 0u) : dn_;     \
                t[k] = (t[k] >> 32) + (ulong)lo_ + g[k];                                    \
                g[k] = 0ul;                                                                 \
            }                                                                               \
        }                                                                                   \
    }                                                                                       \
    NORMALIZE                                                                               \
    COND_SUB                                                                                \
    for (int k = 0; k < K; k++) x[k] = (uint)t[k];                                          \
}

// x = 2x mod n
#define DOUBLE_MOD {                                                                        \
    for (int k = 0; k < K; k++) g[k] = (ulong)(x[k] >> 31);                                 \
    for (int k = 0; k < K; k++) {                                                           \
        uint up_ = simd_shuffle_up((uint)g[k], (ushort)1);                                  \
        uint wr_ = simd_broadcast((uint)g[k > 0 ? k - 1 : 0], (ushort)(SIMD_W - 1));        \
        uint cin_ = (lane == 0u) ? (k > 0 ? wr_ : 0u) : up_;                                \
        t[k] = (ulong)((x[k] << 1) | cin_);                                                 \
    }                                                                                       \
    for (int k = 0; k < K; k++) g[k] = 0ul;                                                 \
    COND_SUB                                                                                \
    for (int k = 0; k < K; k++) x[k] = (uint)t[k];                                          \
}

template <int K>
static inline void fermat_body(device const uint *N, device uint *XS, device uchar *out,
                               uint nl, uint cnt, int bs, int bcount, uint gid, uint lane) {
    uint num = gid / SIMD_W;
    if (num >= cnt) return;                         // whole SIMD groups only: uniform
    device const uint *n = N + (ulong)num * nl;
    device uint *xs = XS + (ulong)num * nl;
    uint x[K], nn[K];
    ulong t[K], g[K];
    for (int k = 0; k < K; k++) {
        uint p = lane + SIMD_W * k;
        x[k] = p < nl ? xs[p] : 0u;
        nn[k] = p < nl ? n[p] : 0u;
        t[k] = 0ul; g[k] = 0ul;
    }
    uint n0 = simd_broadcast(nn[0], (ushort)0);     // -n^-1 mod 2^32 by Newton
    uint xi = n0;
    for (int r = 0; r < 5; r++) xi *= 2u - n0 * xi;
    uint ninv = 0u - xi;
    if (bs >= 0) {
        // exponent n-1, bits bs down to bs-bcount+1 (n is odd, so n-1 differs only in bit 0)
        for (int b = bs; b > bs - bcount && b >= 0; b--) {
            MONT(0)
            uint w = (uint)b >> 5;
            uint myw = 0u;
            for (int k = 0; k < K; k++) if (lane + SIMD_W * k == w) myw = nn[k];
            uint word = simd_broadcast(myw, (ushort)(w % SIMD_W));
            uint eb = (b == 0) ? 0u : ((word >> ((uint)b & 31u)) & 1u);
            if (eb != 0u) DOUBLE_MOD
        }
        for (int k = 0; k < K; k++) { uint p = lane + SIMD_W * k; if (p < nl) xs[p] = x[k]; }
    } else {
        MONT(1)                                     // leave the Montgomery domain
        bool bad = false;
        for (int k = 0; k < K; k++) {
            uint p = lane + SIMD_W * k;
            if (x[k] != (p == 0u ? 1u : 0u)) bad = true;
        }
        bool anybad = simd_any(bad);
        if (lane == 0u) out[num] = anybad ? (uchar)0 : (uchar)1;
    }
}

#define FERMAT_KERNEL(KK)                                                                   \
kernel void fermat_simd_##KK(device const uint *N [[buffer(0)]], device uint *XS [[buffer(1)]], \
                             device uchar *out [[buffer(2)]], constant uint &nl [[buffer(3)]], \
                             constant uint &cnt [[buffer(4)]], constant int &bs [[buffer(5)]], \
                             constant int &bcount [[buffer(6)]],                             \
                             uint gid [[thread_position_in_grid]],                           \
                             uint lane [[thread_index_in_simdgroup]]) {                      \
    fermat_body<KK>(N, XS, out, nl, cnt, bs, bcount, gid, lane);                            \
}

// K = limbs per lane: numbers up to 32*K - 2 limbs (K = 6 covers 4001#, K = 17 covers 12007#)
FERMAT_KERNEL(1)  FERMAT_KERNEL(2)  FERMAT_KERNEL(3)  FERMAT_KERNEL(4)  FERMAT_KERNEL(5)
FERMAT_KERNEL(6)  FERMAT_KERNEL(7)  FERMAT_KERNEL(8)  FERMAT_KERNEL(9)  FERMAT_KERNEL(10)
FERMAT_KERNEL(11) FERMAT_KERNEL(12) FERMAT_KERNEL(13) FERMAT_KERNEL(14) FERMAT_KERNEL(15)
FERMAT_KERNEL(16) FERMAT_KERNEL(17) FERMAT_KERNEL(18) FERMAT_KERNEL(19) FERMAT_KERNEL(20)
FERMAT_KERNEL(21) FERMAT_KERNEL(22) FERMAT_KERNEL(23) FERMAT_KERNEL(24)
