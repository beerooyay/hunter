# the hunter

A prime gap record hunter written in [Praetor](https://github.com/ceeboozwah/Praetor), with an Apple GPU (Metal) path.
One program: `./hunter` starts the control room in your browser, and the control room runs the hunt.

Built by RB Labs (Blaize Rouyea, Corey Bourgeois) with Claude.

## What it does

A *prime gap* is the run of composites between two consecutive primes. The record table at
[primegaps.cloudygo.com](https://primegaps.cloudygo.com/) keeps, for every gap size, the largest *merit*
(gap / ln p) anyone has found. The hunter looks for new entries:

1. **Centers.** It searches around numbers N = m · P# / d (P# is the product of the primes up to P),
   which are divisible by almost every small prime, so their neighbourhoods are unusually prime-poor.
2. **Sieve.** For each center it removes every neighbour with a prime factor below 10^9, using a
   combined sieve plus a Euclid-style modular search for the large primes.
3. **Score.** A survivor is prime with probability q = 1 / (ln N · ∏(1 − 1/p)). On real data this model
   is calibrated to about 1% (the dashboard re-checks it live). From the survivor lists the hunter computes
   the exact probability that a center holds a record.
4. **Test, but only where it pays.** Each center is tested only if its expected value beats λ × its cost,
   and the left side is searched only if the right side left it worth finishing (the stopping rule).
5. **Learn where to look.** A Thompson-sampling learner over (P, d) prices every arm with a cheap
   sieve-only dry run, then shifts the cores toward whatever is actually producing records per core-hour.
6. **Verify.** Every record is re-checked by an independent program (`hunter verify`: BPSW-style tests on
   both ends and GMP's `nextprime`) before you submit it.

## Setup on a Mac (once)

```sh
# 1. tools: compilers, GMP, Rust (Praetor's bootstrap compiler is written in Rust)
xcode-select --install          # skip if you already have it
brew install gmp rust

# 2. Praetor
git clone https://github.com/ceeboozwah/Praetor ~/Praetor
~/Praetor/scripts/install.sh    # installs `ourc` and `our` into ~/.local/bin
export PATH="$HOME/.local/bin:$PATH"   # add this line to ~/.zshrc too

# 3. the hunter
git clone https://github.com/beerooyay/hunter ~/hunter
cd ~/hunter
./build.sh test                 # builds ./hunter, then checks the GPU kernel's math against GMP (~1 min)
./hunter bench                  # CPU vs GPU speed on this machine, plus a math check on the real GPU
./hunter                        # the control room: run this on its own line, it opens http://localhost:8765
```

If `scripts/install.sh` gives you trouble, this works too:
`cd ~/Praetor && cargo build --release -p ourc`, then build the hunter with
`OURC=~/Praetor/target/release/ourc OUR_RUNTIME=~/Praetor/compiler/runtime ./build.sh test`.

**Bringing your old data over.** `FOUND.tsv`, `VERIFIED.tsv` and `gaps.tsv` use the same columns as the
Python v3 hunter, so copy them into this folder and the dashboard picks them up. The learner starts fresh
and re-prices the arms in its first few minutes.

## Using it

Pick cores, hours and job length in the top bar, tick the arms you want in **where to hunt**, and press
**start hunt**. Closing the browser tab doesn't stop anything. Ctrl-C in the terminal stops the hunt;
records already found are safe in `FOUND.tsv`.

- **records:** each find with its verification status and its standing on the live table. **check live table**
  downloads the current table, which also refreshes `records.txt`. **copy** gives you the submission line.
- **live cores:** what every worker is doing right now.
- **is the model honest:** measured vs predicted prime density on both sides, calibration of high-merit
  predictions, and tail checks. If these drift, the model is wrong and the hunter is wasting time.
- **where to hunt:** the learner's 90% band for every arm's records per core-hour.

## Commands

| command | what it does |
|---|---|
| `./hunter` or `./hunter serve [port]` | the control room (default port 8765, or set `HUNTER_PORT`) |
| `./hunter bench [P d count]` | CPU (GMP) vs GPU throughput, and agreement with GMP |
| `./hunter verify 'm*P#/d-a' gap` | independent check of one gap, appended to `VERIFIED.tsv` |
| `./hunter hunt P d m0 M SL L lambda mcal records.txt` | one engine job (what each worker runs) |

`HUNTER_GPU=1` makes a `hunt` job use Metal, and `HUNTER_GPU=ref` runs the same wavefront code path on the
CPU reference (for validation on machines without a GPU). In the control room the **gpu** toggle adds one
GPU worker next to the CPU cores.

## Files

| file | contents |
|---|---|
| `src/hunter.lang` | everything that thinks: engine, fixed-point math, learner, scheduler, HTTP server (Praetor) |
| `rt/hunter_rt.c` | the thin C layer: clocks, GMP handles, process spawning, poll, file I/O |
| `rt/fermat.metal` | the GPU kernels (Montgomery base-2 Fermat tests, one thread per number) |
| `rt/hunter_metal.m` | Metal host code: compiles `fermat.metal` at runtime, dispatches batches |
| `rt/test_msl.cpp` | runs the exact `fermat.metal` source on the CPU and checks it against GMP |
| `ui.html` | the control room |
| `records.txt` | the record table snapshot (refreshed from the live table by the dashboard) |
| `python-v3/` | the previous Python + C hunter (v3.1), kept as a fallback |

Runtime files (`FOUND.tsv`, `VERIFIED.tsv`, `gaps.tsv`, `jobs.tsv`, `state.tsv`, `hunt.log`, `run/`) stay
on your machine and are ignored by git.

## Safety rails

- No record table means no hunt. Without `records.txt` every gap would look like a record, so the engine
  refuses to run, and the server fetches the table first.
- A GPU batch that fails is redone on the CPU. A prime missed by the GPU would fake a longer gap, so a
  failed dispatch is never trusted.
- Every GPU "probable prime" is confirmed with GMP before it is used.
- If workers keep failing, the hunt pauses and the log says where to look, instead of respawning forever.

## Status of the GPU path

- **Kernel design (v2).** One SIMD group (32 lanes) cooperates on each number, holding it in
  registers (a 1,706-digit number is 6 limbs per lane). Montgomery multiplication runs with
  carry-save accumulators, and only 32-bit values move between lanes. The exponent is walked in
  short dispatches of about 40 ms each, so the GPU never runs one long command.
- **Verified on the CPU.** `./build.sh test` runs the exact `fermat.metal` source with emulated SIMD
  groups of width 2, 4 and 32 (real threads, real shuffles) and gets 0 mismatches against GMP. That
  includes Carmichael numbers and other base-2 pseudoprimes, real primes, and chunked walks of the
  exponent.
- **On an M4 Max:** Apple's Metal compiler accepted the first kernel. The first kernel (one thread per
  number) was far too slow per thread, which is why v2 exists. `./hunter bench` measures v2. It is
  time-boxed, so it can't hang the machine.
- The Praetor wavefront path that feeds the GPU produces the same output as the sequential CPU path
  in every mathematical column. If a GPU batch ever fails, the hunter redoes that batch with GMP.
