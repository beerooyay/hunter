#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>

double rt_logtarget(double, uint64_t, const uint32_t *, uint64_t,
                    const uint32_t *, uint64_t);

int main(void) {
    uint32_t right[] = {2, 8}, left[] = {3, 9};
    for (uint64_t gap = 0; gap < 20; ++gap) {
        double expected = 0;
        for (int i = 0; i < 2; ++i)
            for (int j = 0; j < 2; ++j)
                if (right[i] + left[j] >= gap)
                    expected += .0625 * pow(.75, i + j);
        double actual = rt_logtarget(.25, gap, right, 2, left, 2);
        if (expected) assert(fabs(actual - log(expected)) < 1e-12);
        else assert(isinf(actual) && actual < 0);
    }
    uint32_t offsets[1000];
    for (int i = 0; i < 1000; ++i) offsets[i] = i + 1;
    double rare = rt_logtarget(.5, 2000, offsets, 1000, offsets, 1000);
    assert(isfinite(rare) && fabs(rare + 2000 * log(2)) < 1e-10);
    assert(isinf(rt_logtarget(.5, 1, offsets, 0, offsets, 1000)));
    puts("probe: enumeration, impossible windows, empty sides, and 2^-2000 passed");
}
