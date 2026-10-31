# rb labs gap hunter (v3)

A prime gap hunter that learns where to look, with a browser control room.

## Quick start (Mac)

```bash
brew install gmp python && pip3 install --user gmpy2
cd ~/Desktop/gap-hunter
cc -O3 -o hunt hunt.c -I/opt/homebrew/include -L/opt/homebrew/lib -lgmp -lm
python3 selftest.py            # must say PASS
python3 hunter_ui.py           # opens http://localhost:8765
```

Everything else happens in the control room:

- start and stop hunts
- watch every core live
- see records as they land, with background verification
- check them against the live record table
- copy submission lines and mark them submitted

Closing the page does not stop a hunt.

Headless still works:

```bash
caffeinate -i python3 brain.py --hours 8 --cores 14
```

To stop a headless hunt, `touch STOP` stops it gracefully, or `echo now > STOP` stops it immediately.

## Upgrading from v2

Copy the new files over the old ones. `gaps.tsv`, `hunt_state.json`, `FOUND.tsv` and `VERIFIED.tsv` all carry over. Then rebuild `hunt`; `hunt.c` changed.

## What the first 10 core-hours taught us (5,929 tested centers, 1,707 digits)

1. **The survivor model is exact.**
   - After sieving to 1e9, each survivor is prime with probability q = 1/(ln N · ∏(1−1/p)).
   - Measured ÷ predicted: right side 1.009 ± 0.013, left side 0.985 ± 0.022.
   - The tails are uniform down to 1-in-1000.
   - So survivors behave independently. All the correlation structure of the primes is carried by the small primes the sieve already removed, which is the random-sieve dictionary seen in real data.
   - Practical payoff: a setup can be *priced* with a sieve-only dry run, no prime tests needed.
2. **35% of all time was overhead.**
   - Every 90-second batch restarted 14 processes. Each one rebuilt primes to 1e9, recomputed residues and made a full modular-search pass, then waited at a batch barrier for the slowest core.
   - v3 fixes this with ~10-minute jobs and a continuous worker pool (no barrier). Overhead is about 3%.
3. **The one-sided stopping rule is the biggest win in the engine.**
   - 62% of centers are dropped after the first side.
   - That costs 3.4% of the expected records and saves ~55% of the prime tests.
4. **Ranking within a setup barely matters.** The top tenth of centers by score is only ~2× better than the bottom tenth, so where you hunt beats how you rank.
5. **The divisor matters a lot, and 210 wins.** Policy-aware dry runs (260 centers each):

   | P | d=210 | d=2310 | d=30030 |
   |---|---|---|---|
   | 4001 | 0.37 | 0.33 | 0.23 |
   | 6007 | 0.42 | 0.34 | 0.29 |
   | 8009 | 0.34 | 0.31 | 0.24 |
   | 12007 | 0.46 | | |

   Values are model records per core-hour on the test box, overhead included. Size is a near-wash between 1,700 and 5,100 digits.
6. **Luck so far:** 5 records against 2.7 expected, roughly a 1-in-8 run.

## What changed in v3

- **hunt.c**
  - Policy-aware testing: a center is tested iff the value of the exact "next prime, then continue only if still worth it" policy beats λ × its expected cost.
  - Uses the measured PRP time.
  - Reports CPU time.
  - Faster direct-versus-modular-search crossover.
- **brain.py**
  - Continuous worker pool.
  - Sieve-only dry-run pricing of every setup seeds a Thompson-sampling posterior. Dry prices are rescaled by the measured price-to-reality factor.
  - λ is taken from achieved rates only, so it can never starve testing.
  - Records are written and verified the moment they're found.
  - `status.json` feeds the UI.
- **hunter_ui.py + ui.html**
  - The control room.
  - "Is the model still honest?" re-measures the survivor calibration live on every run.

## Honest lineage

The core method is Seth Troisi's prime-gap toolkit (github.com/sethtroisi/prime-gap). That includes:

- combined sieve over m·P#/d with a modular search
- prob(record) ranking
- a one-sided skip

Ours adds:

- the learner across setups with dry-run pricing
- a stopping threshold tied to the rate actually achieved
- live calibration
- the control room

## Submitting

- Use the "copy open lines" button, then paste at primegaps.cloudygo.com with your name in "discoverer".
- Tap **add** once.
- Then use "mark open as submitted". Double submissions can get stuck as "Already processed".
