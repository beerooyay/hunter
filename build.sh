#!/usr/bin/env bash
# build.sh -- builds ./hunter (Praetor + a thin C runtime, + Metal on macOS)
#   ./build.sh          build
#   ./build.sh test     build, then check the gpu kernel's math on the cpu against gmp
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p build build/shim
OURC=${OURC:-ourc}
if ! command -v "$OURC" >/dev/null 2>&1; then
  echo "can't find the praetor compiler (ourc). install it first -- see README.md, step 1."; exit 1
fi
# praetor -> llvm ir (this also unpacks the toolchain's runtime C files on first use)
cat src/hunter.lang src/brain.lang > build/hunter-combined.lang
"$OURC" build/hunter-combined.lang --show-llvm > build/hunter.ll 2> build/ourc.log || true
if ! grep -q "define" build/hunter.ll; then cat build/ourc.log; exit 1; fi
RT=${OUR_RUNTIME:-}
if [ -z "$RT" ]; then
  RT=$(ls -d "${OUR_HOME:-$HOME/.our}"/lib/*/runtime 2>/dev/null | tail -1 || true)
fi
if [ -z "$RT" ] || [ ! -f "$RT/mmlrt_common.c" ]; then echo "can't find the praetor runtime; set OUR_RUNTIME=<praetor clone>/compiler/runtime"; exit 1; fi
CFLAGS="-O2 -w"
GMP_INC=""; GMP_LIB=""
if [ "$(uname)" = "Darwin" ]; then
  BREW=$(brew --prefix 2>/dev/null || echo /opt/homebrew)
  GMP_INC="-I$BREW/include"; GMP_LIB="-L$BREW/lib"
  clang $CFLAGS -DHUNTER_METAL $GMP_INC -c rt/hunter_rt.c -o build/hunter_rt.o
  # embed rt/fermat.metal as a C string; Metal compiles it at runtime
  sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' -e 's/^/"/' -e 's/$/\\n"/' rt/fermat.metal > build/fermat_msl.inc
  clang $CFLAGS -fobjc-arc $GMP_INC -Ibuild -c rt/hunter_metal.m -o build/hunter_metal.o
  EXTRA="build/hunter_metal.o -framework Metal -framework Foundation"
  PLAT="$RT/mmlrt_posix.c"
else
  clang $CFLAGS -c rt/hunter_rt.c -o build/hunter_rt.o
  EXTRA="-lpthread"
  PLAT="$RT/mmlrt_posix.c"
fi
clang $CFLAGS -c build/hunter.ll -o build/hunter.o
clang $CFLAGS -c "$RT/mmlrt_common.c" -o build/mmlrt_common.o
clang $CFLAGS -c "$PLAT" -o build/mmlrt_plat.o
clang build/hunter.o build/mmlrt_common.o build/mmlrt_plat.o build/hunter_rt.o $EXTRA $GMP_LIB -lgmp -lm -o hunter
echo "built ./hunter"
if [ "${1:-}" = "test" ]; then
  # run the exact gpu kernel source on the cpu, with emulated simd groups of width 2, 4 and 32
  echo 'namespace metal {}' > build/shim/metal_stdlib
  sed -E 's/\[\[[^]]*\]\]//g' rt/fermat.metal > build/fermat_cpu.h
  for W in 2 4 32; do
    clang++ -std=c++17 -O2 -w -DSIMD_W=$W $GMP_INC -Ibuild/shim -Ibuild rt/test_msl.cpp $GMP_LIB -lgmp -lpthread -o build/test_msl_$W
    ./build/test_msl_$W
  done
fi
