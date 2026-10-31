# Notes for Corey: building the hunter in Praetor

The hunter is about 2,700 lines of Praetor in `src/hunter.lang`. That includes the sieve and scoring engine,
all of its fixed-point arithmetic, the Thompson-sampling learner, the process scheduler, and the HTTP
control room. Underneath it is about 300 lines of C (`rt/hunter_rt.c`) for things the stdlib doesn't
cover yet, plus the Metal host code and kernel.

The engine is a port of a C engine we had already validated. On the same inputs the Praetor engine's output
matches the C engine's to every printed digit (survivors, gaps, test counts, probabilities). On the same
job its sieve took 13.7 s against C's 17.8 s; its scoring took 2.0 s against 0.9 s, because of the
fixed-point math (see the wishlist).

## What the C layer does, and why

| need | why it's in C for now |
|---|---|
| GMP integers | `mpz_t` is a struct, so Praetor holds an opaque `*void` from `rt_mpz()` and calls `__gmpz_*` directly |
| per-thread CPU clock, monotonic clock | not in std yet |
| `poll` + `accept`/`recv` with a timeout | the server is a single-threaded event loop; std.net only blocks |
| spawn a worker without waiting, reap it later | `std.process.run` waits; the scheduler needs `posix_spawn` + `waitpid(WNOHANG)` |
| `pread`, append, atomic write-then-rename | small conveniences over std.fs |
| Metal | Objective-C, linked with `-framework Metal -framework Foundation` |

## Things that bit us (ourc 0.2.x)

1. **Codegen bug.** A `match` whose arms all `return` a `str` produced invalid LLVM IR. The workaround is
   in `arg_or`: assign inside the arms and return after the match.
2. **`handle` as a function name** fails to parse at the *call site* with "expected `)`, found `,`". It's
   presumably reserved. An error that names the keyword would have saved a few minutes.
3. **`let x = "literal";` gives `*const u8`, not `str`**, so `.len` and `.bytes` fail with a field-access
   error. `let x: str = "..."` works. This is surprising, since literals passed straight to a `str`
   parameter are fine.
4. **E1001 after `p.bytes.ptr` goes to an extern.** The borrow stays live, so using `p` later in the same
   function fails. A one-line helper `fn f(p: str) -> i64 { return ext(p.bytes.ptr); }` gets around it.
5. **`f(s, ..., s.field)` where `f` takes `write s`** gives "use of moved authority". That's fair, but a
   hint ("bind `s.field` to a local first") would help.
6. **A false "use of uninitialized `e[i]`"** on `let e = ex.bytes;` (with `ex` from `process.arg`), inside
   loops after `e` had been passed to a function. Moving the loop into a helper that takes `e: slice u8`
   fixed it.
7. **Very large integer literals** were rejected in some positions; computing them at runtime works.

## Wishlist, in order of how much code it would delete

1. **`f64`.** With no floats, everything is fixed point: Q62 probabilities, Q40 rates, signed Q32 logs,
   128-bit products built from 32-bit halves, plus hand-written `ln`, `exp` and `isqrt`. That's about
   300 lines that a float type would remove.
2. **`u128` or a `mulhi` intrinsic.** It would make `mulw`/`muldiv` one line each and much faster.
3. **std.process spawn + try_wait**, with env and stdout redirection.
4. **Timeouts in std.net** (accept/recv with a deadline, or a `poll` wrapper).
5. **Link flags in source or the project file** (`-lgmp`, `-framework Metal`), so `our build` could replace
   `build.sh`.

## What was great

- `extern fn` with raw pointers plus `slice(p, n)` made the port mechanical. The engine works on big
  `rt_alloc*` buffers through bounds-checked slices, so a bad index panics instead of corrupting memory.
- The `write` parameter mode made it obvious which functions mutate the engine context. The server's state
  (`struct Srv`) uses the same discipline.
- `--show-llvm` + clang meant the build could link C, Objective-C and Praetor objects together with no
  special support.
