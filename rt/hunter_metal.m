// hunter_metal.m -- the Apple GPU path: batched base-2 Fermat tests in Metal.
//
// Praetor calls rt_gpu_available / rt_gpu_fermat_batch through FFI. The kernel source
// (rt/fermat.metal) is embedded at build time and compiled at runtime by the OS Metal compiler.
// Two kernels, same math as rt_fermat_one in hunter_rt.c (validated against GMP):
//   fermat_dev -- one thread per number, scratch in device memory, struct-of-arrays layout
//                 so neighbouring threads touch neighbouring words
//   fermat_tg  -- one thread per number, scratch in threadgroup (on-chip) memory; faster
//                 for smaller numbers, limited by 32 KB of threadgroup memory per group
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// the kernel source lives in rt/fermat.metal; build.sh turns it into a C string (build/fermat_msl.inc)
static const char *kSrcC =
#include "fermat_msl.inc"
;
#define kSrc [NSString stringWithUTF8String:kSrcC]

static id<MTLDevice> gDev = nil;
static id<MTLCommandQueue> gQ = nil;
static id<MTLComputePipelineState> gDevPSO = nil, gTgPSO = nil;
static int gInit = 0;
static char gName[256] = "none";
static char gErr[1024] = "";

int rt_gpu_available(void) {
    if (gInit) return gDev != nil && gDevPSO != nil;
    gInit = 1;
    @autoreleasepool {
        gDev = MTLCreateSystemDefaultDevice();
        if (!gDev) { snprintf(gErr, sizeof gErr, "no Metal device"); return 0; }
        snprintf(gName, sizeof gName, "%s", [[gDev name] UTF8String]);
        NSError *err = nil;
        MTLCompileOptions *opt = [MTLCompileOptions new];
        id<MTLLibrary> lib = [gDev newLibraryWithSource:kSrc options:opt error:&err];
        if (!lib) { snprintf(gErr, sizeof gErr, "metal compile failed: %s", [[err localizedDescription] UTF8String]); gDev = nil; return 0; }
        id<MTLFunction> fd = [lib newFunctionWithName:@"fermat_dev"];
        id<MTLFunction> ft = [lib newFunctionWithName:@"fermat_tg"];
        if (!fd) { snprintf(gErr, sizeof gErr, "kernel fermat_dev missing from the compiled library"); gDev = nil; return 0; }
        gDevPSO = [gDev newComputePipelineStateWithFunction:fd error:&err];
        if (!gDevPSO) { snprintf(gErr, sizeof gErr, "pipeline failed: %s", err ? [[err localizedDescription] UTF8String] : "?"); gDev = nil; return 0; }
        if (ft) gTgPSO = [gDev newComputePipelineStateWithFunction:ft error:&err];   // optional: device-scratch kernel suffices
        gQ = [gDev newCommandQueue];
    }
    return gDev != nil && gDevPSO != nil;
}

const char *rt_gpu_name(void) { rt_gpu_available(); return gDev ? gName : gErr; }
const char *rt_gpu_error(void) { return gErr; }

// mode: 0 = auto, 1 = device scratch, 2 = threadgroup scratch
static int gMode = 0;
void rt_gpu_set_mode(int m) { gMode = m; }

int rt_gpu_fermat_batch(const uint32_t *nums, const uint32_t *rmods, int nl, int count, uint8_t *out) {
    if (count <= 0) return 0;
    if (!rt_gpu_available()) return -1;
    @autoreleasepool {
        size_t words = (size_t)nl * count;
        id<MTLBuffer> bN = [gDev newBufferWithLength:words * 4 options:MTLResourceStorageModeShared];
        id<MTLBuffer> bR = [gDev newBufferWithLength:words * 4 options:MTLResourceStorageModeShared];
        id<MTLBuffer> bO = [gDev newBufferWithLength:count options:MTLResourceStorageModeShared];
        uint32_t *pn = (uint32_t *)[bN contents], *pr = (uint32_t *)[bR contents];
        for (int i = 0; i < count; i++)            // array-of-structs -> struct-of-arrays
            for (int j = 0; j < nl; j++) {
                pn[(size_t)j * count + i] = nums[(size_t)i * nl + j];
                pr[(size_t)j * count + i] = rmods[(size_t)i * nl + j];
            }
        uint32_t unl = (uint32_t)nl, ucnt = (uint32_t)count;
        size_t perThread = (2 * (size_t)nl + 2) * 4;
        NSUInteger tgFit = 32768 / perThread;
        int mode = gMode;
        if (mode == 0) mode = (tgFit >= 16 && gTgPSO) ? 2 : 1;
        if (mode == 2 && (!gTgPSO || tgFit < 1)) mode = 1;
        id<MTLCommandBuffer> cb = [gQ commandBuffer];
        id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
        [enc setBuffer:bN offset:0 atIndex:0];
        [enc setBuffer:bR offset:0 atIndex:1];
        [enc setBuffer:bO offset:0 atIndex:4];
        [enc setBytes:&unl length:4 atIndex:5];
        [enc setBytes:&ucnt length:4 atIndex:6];
        id<MTLBuffer> bX = nil, bT = nil;
        if (mode == 2) {
            NSUInteger tg = tgFit;
            if (tg > [gTgPSO maxTotalThreadsPerThreadgroup]) tg = [gTgPSO maxTotalThreadsPerThreadgroup];
            if (tg > 32) tg = 32;
            [enc setComputePipelineState:gTgPSO];
            [enc setThreadgroupMemoryLength:((tg * perThread + 15) / 16) * 16 atIndex:0];
            [enc dispatchThreads:MTLSizeMake(count, 1, 1) threadsPerThreadgroup:MTLSizeMake(tg, 1, 1)];
        } else {
            bX = [gDev newBufferWithLength:words * 4 options:MTLResourceStorageModePrivate];
            bT = [gDev newBufferWithLength:((size_t)nl + 2) * count * 4 options:MTLResourceStorageModePrivate];
            [enc setComputePipelineState:gDevPSO];
            [enc setBuffer:bX offset:0 atIndex:2];
            [enc setBuffer:bT offset:0 atIndex:3];
            NSUInteger tg = [gDevPSO threadExecutionWidth];
            [enc dispatchThreads:MTLSizeMake(count, 1, 1) threadsPerThreadgroup:MTLSizeMake(tg, 1, 1)];
        }
        [enc endEncoding];
        [cb commit];
        [cb waitUntilCompleted];
        if ([cb status] != MTLCommandBufferStatusCompleted) {
            snprintf(gErr, sizeof gErr, "gpu command failed: %s", [[[cb error] localizedDescription] UTF8String]);
            return -2;
        }
        memcpy(out, [bO contents], count);
        return mode;
    }
}
