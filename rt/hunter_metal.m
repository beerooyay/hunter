// hunter_metal.m -- the Apple GPU path: batched base-2 Fermat tests in Metal.
//
// Praetor calls rt_gpu_available / rt_gpu_fermat_batch through FFI. The kernel source
// (rt/fermat.metal) is embedded at build time and compiled at runtime by the OS Metal compiler.
//
// One SIMD group of 32 lanes works on each number (see fermat.metal). The exponent is walked in
// short chunks, one command buffer each, sized adaptively to ~40 ms, so the GPU never runs one
// long command (which would stall the display and trip macOS's GPU watchdog), and a caller can
// put a time budget on a batch (the bench does; the hunter doesn't).
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

uint64_t rt_now_ns(void);   // hunter_rt.c

// the kernel source lives in rt/fermat.metal; build.sh turns it into a C string (build/fermat_msl.inc)
static const char *kSrcC =
#include "fermat_msl.inc"
;

#define KMAX 24              // kernels exist for 1..24 limbs per lane: numbers up to 766 limbs
static id<MTLDevice> gDev = nil;
static id<MTLCommandQueue> gQ = nil;
static id<MTLLibrary> gLib = nil;
static id<MTLComputePipelineState> gPSO[KMAX + 1];
static int gInit = 0;
static char gName[256] = "none";
static char gErr[1024] = "";
static uint64_t gBudgetNs = 0;   // 0 = no limit

static id<MTLComputePipelineState> pso_for(int K) {
    if (K < 1 || K > KMAX) { snprintf(gErr, sizeof gErr, "numbers this large need more than %d limbs per lane", KMAX); return nil; }
    if (gPSO[K]) return gPSO[K];
    char nm[64];
    snprintf(nm, sizeof nm, "fermat_simd_%d", K);
    id<MTLFunction> f = [gLib newFunctionWithName:[NSString stringWithUTF8String:nm]];
    if (!f) { snprintf(gErr, sizeof gErr, "kernel %s missing from the compiled library", nm); return nil; }
    NSError *err = nil;
    id<MTLComputePipelineState> p = [gDev newComputePipelineStateWithFunction:f error:&err];
    if (!p) { snprintf(gErr, sizeof gErr, "pipeline %s failed: %s", nm, err ? [[err localizedDescription] UTF8String] : "?"); return nil; }
    if ([p threadExecutionWidth] != 32) {
        snprintf(gErr, sizeof gErr, "this gpu runs %lu-wide simd groups; the kernel is written for 32", (unsigned long)[p threadExecutionWidth]);
        return nil;
    }
    gPSO[K] = p;
    return p;
}

int rt_gpu_available(void) {
    if (gInit) return gLib != nil;
    gInit = 1;
    @autoreleasepool {
        gDev = MTLCreateSystemDefaultDevice();
        if (!gDev) { snprintf(gErr, sizeof gErr, "no Metal device"); return 0; }
        snprintf(gName, sizeof gName, "%s", [[gDev name] UTF8String]);
        NSError *err = nil;
        MTLCompileOptions *opt = [MTLCompileOptions new];
        gLib = [gDev newLibraryWithSource:[NSString stringWithUTF8String:kSrcC] options:opt error:&err];
        if (!gLib) { snprintf(gErr, sizeof gErr, "metal compile failed: %s", err ? [[err localizedDescription] UTF8String] : "?"); return 0; }
        gQ = [gDev newCommandQueue];
        if (!pso_for(6)) { gLib = nil; return 0; }     // build the common size now so errors show early
    }
    return gLib != nil;
}

const char *rt_gpu_name(void) { rt_gpu_available(); return gLib ? gName : gErr; }
const char *rt_gpu_error(void) { return gErr; }
void rt_gpu_set_mode(int m) { (void)m; }                // one kernel now; kept for the ABI
void rt_gpu_set_budget_ms(int ms) { gBudgetNs = ms > 0 ? (uint64_t)ms * 1000000ull : 0; }

// returns 3 (the simd kernel) on success; < 0 on failure, with the reason in rt_gpu_error():
//   -1 no gpu, -2 command failed, -3 no kernel for this size, -4 time budget exceeded
int rt_gpu_fermat_batch(const uint32_t *nums, const uint32_t *rmods, int nl, int count, uint8_t *out) {
    if (count <= 0) return 0;
    if (!rt_gpu_available()) return -1;
    int K = (nl + 2 + 31) / 32;
    @autoreleasepool {
        id<MTLComputePipelineState> pso = pso_for(K);
        if (!pso) return -3;
        size_t words = (size_t)nl * count;
        id<MTLBuffer> bN = [gDev newBufferWithLength:words * 4 options:MTLResourceStorageModeShared];
        id<MTLBuffer> bX = [gDev newBufferWithLength:words * 4 options:MTLResourceStorageModeShared];
        id<MTLBuffer> bO = [gDev newBufferWithLength:(NSUInteger)count options:MTLResourceStorageModeShared];
        if (!bN || !bX || !bO) { snprintf(gErr, sizeof gErr, "could not allocate gpu buffers"); return -2; }
        memcpy([bN contents], nums, words * 4);
        memcpy([bX contents], rmods, words * 4);          // the running value starts at R mod n
        int top = 0;                                      // highest set bit over the batch
        for (int i = 0; i < count; i++) {
            const uint32_t *n = nums + (size_t)i * nl;
            int w = nl - 1;
            while (w > 0 && n[w] == 0) w--;
            int b = 31;
            while (b > 0 && !((n[w] >> b) & 1u)) b--;
            if (w * 32 + b > top) top = w * 32 + b;
        }
        NSUInteger tg = [pso maxTotalThreadsPerThreadgroup];
        if (tg > 256) tg = 256;
        tg -= tg % 32;
        if (tg < 32) tg = 32;
        MTLSize grid = MTLSizeMake((NSUInteger)count * 32, 1, 1), tgs = MTLSizeMake(tg, 1, 1);
        uint32_t unl = (uint32_t)nl, ucnt = (uint32_t)count;
        int bs = top, chunk = 4;
        uint64_t t0 = rt_now_ns();
        for (;;) {
            int32_t b = bs < 0 ? -1 : bs, c = bs < 0 ? 0 : chunk;
            uint64_t c0 = rt_now_ns();
            id<MTLCommandBuffer> cb = [gQ commandBuffer];
            id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
            [enc setComputePipelineState:pso];
            [enc setBuffer:bN offset:0 atIndex:0];
            [enc setBuffer:bX offset:0 atIndex:1];
            [enc setBuffer:bO offset:0 atIndex:2];
            [enc setBytes:&unl length:4 atIndex:3];
            [enc setBytes:&ucnt length:4 atIndex:4];
            [enc setBytes:&b length:4 atIndex:5];
            [enc setBytes:&c length:4 atIndex:6];
            [enc dispatchThreads:grid threadsPerThreadgroup:tgs];
            [enc endEncoding];
            [cb commit];
            [cb waitUntilCompleted];
            if ([cb status] != MTLCommandBufferStatusCompleted) {
                NSError *e = [cb error];
                snprintf(gErr, sizeof gErr, "gpu command failed: %s", e ? [[e localizedDescription] UTF8String] : "?");
                return -2;
            }
            if (bs < 0) break;
            // aim for ~40 ms per command buffer: short enough to keep the display smooth
            uint64_t dt = rt_now_ns() - c0;
            double want = dt > 0 ? (double)chunk * 40e6 / (double)dt : (double)chunk * 2;
            if (want > chunk * 2.0) want = chunk * 2.0;
            if (want < 1) want = 1;
            if (want > 4096) want = 4096;
            chunk = (int)want;
            bs -= c;
            if (bs < 0) bs = -1;
            uint64_t el = rt_now_ns() - t0;
            if (gBudgetNs && el > gBudgetNs) {
                double frac = (double)(top - (bs < 0 ? 0 : bs)) / (double)(top + 1);
                snprintf(gErr, sizeof gErr, "stopped at the %.0f s budget, %.1f%% of the way through; a full batch would take about %.0f s",
                         el / 1e9, 100 * frac, frac > 0 ? el / 1e9 / frac : 0.0);
                return -4;
            }
        }
        memcpy(out, [bO contents], (size_t)count);
        return 3;
    }
}
