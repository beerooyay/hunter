#ifndef HUNTER_SURVIVORS_H
#define HUNTER_SURVIVORS_H
#include <stdint.h>
// Enumerate unset bits in [1, limit], in increasing order. Output capacity >= limit.
static inline uint64_t hunter_survivors(const uint64_t *bits, uint64_t start,
                                       uint64_t limit, uint32_t *out) {
    uint64_t n = 0;
    for (uint64_t word = 0; word <= limit / 64; ++word) {
        uint64_t remaining = ~bits[start + word];
        if (word == 0) remaining &= ~UINT64_C(1);
        if (word == limit / 64 && limit % 64 != 63)
            remaining &= (UINT64_C(1) << (limit % 64 + 1)) - 1;
        while (remaining) {
            out[n++] = (uint32_t)(word * 64 + __builtin_ctzll(remaining));
            remaining &= remaining - 1;
        }
    }
    return n;
}
#endif
