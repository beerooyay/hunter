# Hunter compute lab v1

Start `python3 launch_control.py`, then open http://127.0.0.1:8767/ .
The native server stays on 8766. Both bind only to loopback. Existing local hunt
controls pass through a token-protected proxy; the UI also controls bounded
GitHub evaluation runs. `gh auth status` must succeed on the local machine.
Tokens stay in the gh credential store, never in the page or exports. The page
gets a separate ephemeral local CSRF token. This is not a public multiuser server.

## The actual neural network

`src/brain.lang` implements a six-input, eight-ReLU-unit residual regressor with
Q16 forward/backprop arithmetic and 12 training epochs. It predicts normalized
log endpoint elapsed time under the existing volume stopping policy. Python
prepares data and reports metrics; C only transports integers. This is a small
supervised neural network, not a theorem prover or a self-modifying optimizer.

Run `python3 -m optimizer.brain`. Datasets include interrupted-gap cost
observations; these do not become negative record labels. Duplicate centers
across snapshots are excluded. Entire 10,000-multiplier blocks share one split
(80% train, 10% validation, 10% test by deterministic hash). Features are
pre-endpoint quantities: family, digit length, hazard and the existing cost
estimate. Outcome, merit, hit and completion are not input features. All metrics
use bounded normalized log seconds; this clipping does not measure absolute
CPU savings. Historical wall-time contention and selected-center bias remain.

The first 93,839-row fit has test MSE .027863 vs .035249 baseline, or .028619
for a training-only constant residual correction: 21.0% vs raw baseline, **2.6%**
vs calibrated baseline. These are engineering comparisons, not confidence bounds
or evidence of higher record yield. No model changes production search decisions.
The frozen seed is evaluated on entirely new cloud traces before the cloud model
is fitted. Prospective results are imported and shown separately.

Weights, source fingerprints, code fingerprints, predictions and split identities
are retained under learning/brain/versions. Retraining rebuilds from cumulative
available observations; it does not incrementally continue an optimizer state.
The committed seed is a fixed prospective baseline. A new version must earn its
own fresh evaluation; do not tune repeatedly against the same test split.

## Fleet

The existing hunter-records.yml workflow now builds the pinned Praetor compiler
and Hunter **once**, then distributes the binary to eight or ten Ubuntu workers.
Each performs three ten-minute volume segments with bounded graceful drain.
Checkpoint artifacts retain candidates, native state, job/trial logs and code/run
identity. Native scheduler state persists across segments, seeded from existing
family history; each campaign/retry/shard gets a fresh disjoint multiplier range.
The range formula fails closed for unsupported retries and native word overflow.
A shared trainer follows collection on a separate job, using all available shards.
Native word-wise survivor enumeration remains enabled. Experimental anchors and
adaptive shortlist pruning remain disabled: neither earned production adoption.

These are finite software integration/learner evaluations, not a perpetually
restarted hosted service. There is no cron/relaunch loop. Standard public-repo
Ubuntu runners are used; no paid runners or resources are provisioned. Concurrent
capacity may queue. Always recheck GitHub terms/quotas before changing budgets.
For sustained hunting use the existing self-hosted fleet supervisor on authorized
machines. A local one-shot schedule can request a bounded evaluation within 48
hours. The control service and Mac must remain awake. Due launches are durably
claimed before dispatch; ambiguous failures are surfaced, never blindly retried.

Cloud state refreshes every 90 seconds; search measurements arrive at completed
~10-minute segment uploads, not a real-time stream. Imported artifacts are copied
to isolated, checksummed directories; they never overwrite the active local
hunter state. Candidate TSV exports deduplicate gap/expression, but still require
independent verification and comparison with a current public table. Stored
artifacts are retained seven days remotely; local imports persist.

## A clean path for ideas

Copy optimizer/idea-template.json and give the idea a stable ID. Pin its baseline,
input/table hashes, predecision features and exact preservation contract. Register
it in optimizer/experiments.json as proposed; implementation stays isolated behind
an explicit experiment switch. Save counterexamples as carefully as successes.

An idea moves through proposed → experimental → shadow → eligible for review.
Adoption requires the mathematical premises to match the implementation, relevant
oracle/certificate tests, and paired whole-cost improvement on unseen ranges.
A Lean proof establishes its stated proposition, not speed, oracle truth or code
refinement. The registry deliberately cannot enable arbitrary native features.
The anchor experiment remains a useful rejected case. There is no novelty claim.
