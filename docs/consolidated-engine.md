# Consolidated Hunter: fleet accounting and incremental deepening

This branch integrates the local shared learner, unified dashboard and experiments
with the self-hosted fleet supervisor from PR12. Existing GitHub campaign refs
and jobs are untouched. No perpetual hosted workflow or public reporting is enabled.

## Native persistent probe

`hunter probe-worker P d capacity target start max_depth` retains prime lists,
primorial residues, calibrated setup and scratch allocation. With HUNTER_PATTERNS=1,
stdin accepts `start count depth selected_count [zero-based selected indices...]`.
A zero selected_count starts a fresh full batch. A positive count requires the
same retained batch, a greater depth, and a batch fitting in allocated memory.
Only the new prime suffix is applied; unselected windows are not deepened or
returned. A filtered batch cannot be reused for another refinement: begin a new
full request first. Each response ends with @cost CPU/wall nanoseconds and
`probe complete`. @setup reports initial CPU cost. Closing stdin exits.

The prime sieve, incremental striking and survivor output execute in Praetor.
C supplies IO and OS timing. Python orchestrates the comparison and evaluates
endpoints. This is not a claim of an entirely Praetor research pipeline.

Regression tests compare selected incremental survivors, hazard q, logN and
probability scores against fresh full batches and standalone probes at three
multiplier ranges, including 256-window batches. Invalid refinements fail closed.
The ordinary volume route calls the same sieve with no mask and a fresh bitset.

Run `python3 experiments/adaptive_depth.py --cached --seconds 600 --output DIR`.
Use a fresh output directory. Full and adaptive each get an independent persistent
worker; setup is charged once to each. Full sieves all through 10^7. Adaptive
sieves all through 10^6 and deepens its top30% in one incremental batch. Both use
the same pair ranking and select top10%. Raw inputs, outputs, selections and
endpoint-cost replay remain saved. Incomplete final rounds must be excluded
from equal-sample comparisons. Scoring and endpoint costs remain material even
if sieve time improves. This does not yet implement a durable untested-candidate
queue, nor modify production search policy.

## Fleet accounting

Run `python3 fleet_supervisor.py --dry-run` to see the plan. This supervisor is
for an owned/authorized host. Reservations now cover search plus ten minutes
for bounded draining, verification and backup at detected host CPU capacity+1.
Reservations persist and are not refunded after an interrupted invocation.
They are conservative admission control, not an OS-enforced hard CPU quota.
Draining and verification each have a two-minute limit; shutdown remains bounded.

Native status exposes cpu_total_ns: OS user+system CPU of server, reaped children
and live search/verifier/tool children. The supervisor adds its CPU and includes
backup work in per-campaign provisional samples. At final shutdown, OS child
resource usage plus supervisor CPU reconciles the invocation total, including
startup, cooldown and shutdown. Updated native shutdown reaps verifier children.
This final measured CPU total supersedes provisional campaign samples in budget.json.
Per-campaign yield denominators explicitly distinguish reserved worker-hours from
measured CPU-hours. The archive manifest contains the pre-backup sample; a paired
campaign-N-accounting.json contains the post-backup sample. Final invocation
reconciliation is authoritative for cumulative measured CPU.

Late verification of an earlier discovery is no longer counted as a new discovery
for the current campaign. Counts still represent local candidates; certification
and comparison against a fresh public table are separate.

## Backups

Each archive now includes ordinary state/logs/configuration, the conservative
fleet budget ledger and reporting metadata, and learning files,
including shared tables, research trials, patterns and future SQLite caches.
Every SQLite database is copied through SQLite online backup, normalized to a
standalone rollback-journal file, and checked with integrity_check. WAL/SHM and
lock files are excluded. SHA256 checksums cover each archived payload. The archive
is published atomically. Individual databases are transactional snapshots;
no cross-database or cross-file global transaction is claimed.

Tests cover committed WAL data under an open uncommitted writer, successful
restore and checksums, late-verification attribution, native incremental parity,
and a short isolated supervisor campaign with actual native CPU accounting.
