# Persistent learning and the long-shot lab

Ordinary Praetor already saves its family counters, modeled value, CPU time,
last 40 log-rate samples, and next multiplier in `state.tsv`; startup restores
them. Discoveries alone are not the memory. Its reward is **predicted table
improvements per CPU-hour**, not actual observed records per CPU-hour.

The October 31 upgrade repairs an empty-history trap: a zero-test job had been
logged as an almost-zero rate and could suppress future selection. On load,
only wholly untested, zero-value log histories are cleared. Other history and
all positions/counters remain. Each such family gets at most two 20-multiplier
unfiltered CPU trials (field 65 stores attempts); concurrent duplicate cold
trials are excluded. This is bounded exploration, not evidence of higher yield.

## Research worker

`python3 research.py --seconds 28800` starts one low-priority worker; gmpy2 is
required. It scouts with the native Praetor sieve, refines a smaller window,
and tests 3 ranked candidates plus 1 uniform random control from the same fine
window. Targets 30, 40, 50 rotate. Six `(P,d)` families are warm-started for each
target. After warmup, 20% of recipe choices are random exploration; otherwise
the model uses shrunk recent log-yield estimates with uncertainty perturbations.
This is an adaptive statistical model, not a deep neural network.

The recipe reward is modeled target probability divided by **whole-round elapsed
time**, including scouting, sieving, testing, verification, and checkpoint work
before the final round summary. It is not measured rare-hit frequency. Because
this is one worker, elapsed time conservatively includes CPU contention. Rankings
within a family use target probability / expected tests; per-test cost is roughly
constant within that family. Log probabilities avoid fixed-point tail underflow.

`learning/research.sqlite3` stores every finished candidate, finite-window
failures, recipe results, compressed survivor arrays, and independently rechecked
finds. WAL transactions, an exclusive process lock, and reserved round IDs make
restarts safe. Interrupted rounds are labeled and excluded from recipe training;
their committed candidate observations remain. A candidate interrupted mid-test
is not recorded as a failure. Multipliers use deterministic per-round random
seeds and are deduplicated by `(P,d,m)`.

Both sides are fully searched within the finite windows, without the ordinary
record stopping rule. Hazard calibration fits all performed trials, including
censored failures. A deterministic 20% center holdout checks a bounded ±5%
correction; at least 500 training successes, 100 heldout successes, and 2 nats
of heldout gain are required before the research worker applies it. Repeated
checks and adjacent-center dependence make this a conservative engineering
gate, **not** a formal statistical significance test. It calibrates hazards,
not dependencies or the extreme-gap tail. No ordinary-hunter probability is
changed by the research calibration.

The dashboard `/research` displays observed and predicted counts at merits
5, 10, 15, 20, 25, 30, 40, 50, separately for ranked and control samples. Controls
measure ranking within selected windows, not the global scout/refine pipeline.
Compare rates with sample counts, not raw unequal-sized lane totals.

Verified finds are in `learning/found.tsv`; these are candidates against the
local table snapshot (hash retained per trial), not guaranteed current world
records. BPSW and next-prime checks are probable-prime verification, not proofs.
No automatic submission occurs. Original hunter results remain in their normal
files. To stop only the lab, create `learning/STOP`; remove that file before
starting again. SIGTERM also checkpoints and terminates an active native probe.

`python3 calibration.py` audits the ordinary hunter's right-side hazard from
`gaps.tsv`, including non-completed gap searches. It never rewrites state.

## Free hosting and surviving a dead Mac

[GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages)
serves static files. It can host a saved dashboard, but cannot run this native
Praetor/GMP engine or keep an iPhone's browser computing in the background.
No hosted deployment has been created by this upgrade.

`python3 export_learning.py` creates a portable source/data archive and a Pages
snapshot under `build/portable`. The SQLite copy uses the online backup API.
The resulting `pages/` directory can be published as a static website; it clearly
labels its data as a saved snapshot. Keep a copy of the archive off this Mac:
a backup on the same disk does not protect against loss of that disk.

For genuinely independent computation, one possible free host is an
[Oracle Always Free VM](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm).
The documentation checked October 31, 2026 lists A1 capacity equivalent to
2 OCPUs / 12 GB; allocation availability is not guaranteed and idle instances
may be reclaimed. An account and available free capacity are still required.
No account, paid resource, or trial upgrade was created. Stay within resources
explicitly labeled Always Free. Recheck current terms before provisioning.

On a Linux VM: install clang, GMP development libraries, Python with gmpy2, and
the Praetor compiler described in the root README; extract the archive and run
`./build.sh`. The Mac binary is deliberately excluded: rebuild for the host.
Start `HUNTER_NO_OPEN=1 ./hunter serve 8766` and `python3 research.py` under your
process supervisor, allocating one ordinary core and one research core on a
two-core host. Reapply the ordinary hunt start configuration after a server
restart; restoring state does not automatically resume a hunt. A seven-day
research budget can be set with `--seconds 604800` and restarted by a supervisor.
The Linux deployment is prepared, not tested on a provisioned host.

Keep the control API on loopback and access through an authenticated tunnel;
it has no public authentication. Phone access to a private remote worker needs
that tunnel/VPN or a separate authenticated front end. Pages snapshots are
read-only and need no connection to the worker.

[GitHub-hosted Actions jobs have a 6-hour limit](https://docs.github.com/en/actions/reference/limits);
they are not being used as an always-on compute substitute here.

Validation: `python3 -m unittest discover -s rt -p '*learning.py' -v`,
`python3 rt/mooncheck.py`, native build, staged HTTP/state/cold-start tests,
and real bounded probe/research runs. No speedup or merit-30+ discovery is
claimed merely because the architecture is now in place.
