# Volume / 30 / 40 portfolio, version 1

This is a bounded CPU campaign for an owned POSIX machine. The working native
engine and the existing research model are unchanged. The new launcher connects
them with persistent state and durable verification, rather than claiming a new
mathematical algorithm or a demonstrated speedup.

## What is implemented

At 10 search slots, one native volume server gets 7 slots, two independent
research workers target merit 30, and one targets merit 40. The research workers
use the existing 337, 1439 and 4001 primorial families. Their target choices and
history namespaces are separated. The volume lane keeps the four established
6007/8009 families and requests 300-second jobs rather than 60-second jobs.

These are SEARCH slots, not strict CPU quotas. The native engine can spawn
additional verifiers. The launcher refuses a slot count that would leave fewer
than two logical CPUs unused; choose fewer slots on a smaller or busy machine.
It lowers its scheduling priority and disables the GPU for this first version.

A five-hour search is followed by at most five minutes of verification draining,
plus bounded process cleanup. No endless relaunch, remote submission, paid
resource creation, or background service installation is performed.

Each campaign downloads a fresh public record table at startup, records its hash
and retrieval time, and fails closed if that fetch is bad. Verified local finds
are merged into the table every five minutes. The upstream table itself is a
startup snapshot, not a continuously refreshed live feed. Final submission
eligibility still needs a fresh upstream comparison.

State lives in `build/portfolio`, separately from the user's normal hunter files.
Native reservations are initialized once and then reused, including the learned
state. Research databases and seeds persist. No saved state is reset on restart.
A file lock prevents two supervisors from sharing one state directory.

Research candidates are written to `verification/*.json` BEFORE the independent
check. Interrupted checks remain pending. Native candidates remain in FOUND.tsv;
`native-pending.json` explicitly lists unfinished checks. Native backlog is retried
on startup; research backlog is retried during the bounded drain. Successful
checks use probable-prime tests plus next_prime, NOT primality certificates.

## Run on an owned machine

Build the existing hunter and use a Python environment containing gmpy2. Then:

```sh
python3 -m unittest discover -s tests -p test_portfolio.py -v
./launch_portfolio.sh
python3 portfolio.py status
```

The default launch is 10 search slots for 5 hours. Override explicitly:

```sh
SLOTS=6 HOURS=5 PYTHON=python3 ./launch_portfolio.sh
```

The launcher does not modify the user's usual hunt or its state. It does not
check unrelated local CPU load, so stop or account for other heavy work first.
The host must stay awake and powered on. A disconnected remote-control agent
cannot be used to launch or inspect it remotely.

Stop gracefully by creating `build/portfolio/STOP`. To resume, remove that marker
explicitly and run the launcher again. The old histories and reservations remain.
Use a separate state directory only for a deliberately independent experiment.

Status and logs:

- `build/portfolio/status.json`: supervisor, native and research checkpoints.
- `build/portfolio/volume/`: native FOUND.tsv, VERIFIED.tsv, state.tsv and logs.
- `build/portfolio/target-*/learning/`: persistent experiment databases and summaries.
- `build/portfolio/verification/`: durable research verification queue.
- `build/portfolio/verified-candidates.tsv`: best verified representative per gap,
  exported at shutdown. This is not automatically a current-record submission list.

## Validation and remaining work

The new GitHub workflow only runs unit tests, compiles the existing native engine,
compares native/Python target probabilities, and runs two 30-second research
smoke tests. It does NOT launch the production portfolio. Full campaigns are
explicitly blocked on GitHub-hosted runners; use an owned machine or an explicitly
authorized self-hosted runner instead.

Version 1 does NOT implement reusable native sieve caches, the broader-refinement
challenger, residue-construction experiments, new rare-tail calibration, endpoint
certificates, or automatic import of old cloud artifacts. The existing model's
30/40 predictions remain unvalidated; its controls are conditional on selected
refined windows. Observed hits and predicted probabilities must remain separate.
Benchmark this orchestration before claiming any gain in throughput or merit.
