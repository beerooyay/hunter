// fermat.metal -- the Apple GPU kernels: batched base-2 Fermat tests, one thread per number.
// same math as rt_fermat_one in hunter_rt.c (Montgomery CIOS, R = 2^(32*nl)).
// build.sh embeds this file into the binary as a string; Metal compiles it at runtime (no Xcode needed).
// rt/test_msl.cpp compiles this exact file as C++ and checks it against GMP on any machine.
#include <metal_stdlib>
using namespace metal;

// MONT(BONE): X = X * B * R^-1 mod N, B = X (BONE=0) or B = 1 (BONE=1). CIOS, T has nl+2 words.
#define MONT(BONE) { \
    for (uint j = 0; j < nl + 2; j++) T(j) = 0u; \
    for (uint i = 0; i < nl; i++) { \
        ulong c = 0; ulong ai = (ulong)X(i); \
        for (uint j = 0; j < nl; j++) { \
            ulong bj = (BONE) ? (j == 0 ? 1ul : 0ul) : (ulong)X(j); \
            ulong s = (ulong)T(j) + ai * bj + c; T(j) = (uint)s; c = s >> 32; \
        } \
        ulong s0 = (ulong)T(nl) + c; T(nl) = (uint)s0; T(nl + 1) = (uint)(s0 >> 32); \
        uint m = T(0) * ninv; \
        c = ((ulong)T(0) + (ulong)m * (ulong)NN(0)) >> 32; \
        for (uint j = 1; j < nl; j++) { \
            ulong s2 = (ulong)T(j) + (ulong)m * (ulong)NN(j) + c; T(j - 1) = (uint)s2; c = s2 >> 32; \
        } \
        ulong s3 = (ulong)T(nl) + c; T(nl - 1) = (uint)s3; T(nl) = T(nl + 1) + (uint)(s3 >> 32); \
    } \
    bool ge = T(nl) != 0u; \
    if (!ge) { ge = true; for (int j = int(nl) - 1; j >= 0; j--) { uint tj = T(j), nj = NN(j); if (tj != nj) { ge = tj > nj; break; } } } \
    if (ge) { long br = 0; for (uint j = 0; j < nl; j++) { long d = (long)T(j) - (long)NN(j) - br; X(j) = (uint)d; br = d < 0 ? 1 : 0; } } \
    else { for (uint j = 0; j < nl; j++) X(j) = T(j); } \
}

#define DOUBLE_MOD { \
    uint carry = 0u; \
    for (uint j = 0; j < nl; j++) { uint v = X(j); X(j) = (v << 1) | carry; carry = v >> 31; } \
    bool ge = carry != 0u; \
    if (!ge) { ge = true; for (int j = int(nl) - 1; j >= 0; j--) { uint xj = X(j), nj = NN(j); if (xj != nj) { ge = xj > nj; break; } } } \
    if (ge) { long br = 0; for (uint j = 0; j < nl; j++) { long d = (long)X(j) - (long)NN(j) - br; X(j) = (uint)d; br = d < 0 ? 1 : 0; } } \
}

#define FERMAT_BODY { \
    uint n0 = NN(0); uint xi = n0; \
    for (int k = 0; k < 5; k++) xi *= 2u - n0 * xi; \
    uint ninv = 0u - xi; \
    for (uint j = 0; j < nl; j++) X(j) = RMM(j); \
    int top = int(nl) - 1; while (top > 0 && NN(top) == 0u) top--; \
    uint ntop = NN(top); int bit = 31; while (bit > 0 && ((ntop >> uint(bit)) & 1u) == 0u) bit--; \
    for (int w = top; w >= 0; w--) { \
        uint nw = NN(w); \
        for (int b = (w == top ? bit : 31); b >= 0; b--) { \
            MONT(0) \
            uint eb = (w == 0 && b == 0) ? 0u : ((nw >> uint(b)) & 1u); \
            if (eb != 0u) DOUBLE_MOD \
        } \
    } \
    MONT(1) \
    bool ok = X(0) == 1u; \
    for (uint j = 1; j < nl && ok; j++) ok = X(j) == 0u; \
    out[gid] = ok ? 1 : 0; \
}

kernel void fermat_dev(device const uint *N [[buffer(0)]], device const uint *RM [[buffer(1)]],
                       device uint *XS [[buffer(2)]], device uint *TS [[buffer(3)]],
                       device uchar *out [[buffer(4)]], constant uint &nl [[buffer(5)]],
                       constant uint &cnt [[buffer(6)]], uint gid [[thread_position_in_grid]]) {
    if (gid >= cnt) return;
    #define NN(j) N[(j) * cnt + gid]
    #define RMM(j) RM[(j) * cnt + gid]
    #define X(j) XS[(j) * cnt + gid]
    #define T(j) TS[(j) * cnt + gid]
    FERMAT_BODY
    #undef NN
    #undef RMM
    #undef X
    #undef T
}

kernel void fermat_tg(device const uint *N [[buffer(0)]], device const uint *RM [[buffer(1)]],
                      device uchar *out [[buffer(4)]], constant uint &nl [[buffer(5)]],
                      constant uint &cnt [[buffer(6)]], threadgroup uint *sh [[threadgroup(0)]],
                      uint gid [[thread_position_in_grid]], uint lid [[thread_position_in_threadgroup]]) {
    if (gid >= cnt) return;
    uint base = lid * (2 * nl + 2);
    #define NN(j) N[(j) * cnt + gid]
    #define RMM(j) RM[(j) * cnt + gid]
    #define X(j) sh[base + (j)]
    #define T(j) sh[base + nl + (j)]
    FERMAT_BODY
    #undef NN
    #undef RMM
    #undef X
    #undef T
}
