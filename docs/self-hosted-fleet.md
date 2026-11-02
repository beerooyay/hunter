# bounded self-hosted hunter fleet

this is a controller for a machine you own or a compute provider permitting sustained scientific workloads. it is **not** a GitHub-hosted Actions perpetual runner.

## capabilities

- runs existing native Hunter/Praetor with up to the number of CPUs on your host, default ten concurrent internal workers.
- preserves Praetor arm learning and multiplier reservations in state.tsv across campaigns.
- writes progress every 15 minutes to fleet/checkpoints.jsonl and fleet/latest.json.
- optionally updates one GitHub issue with safe aggregates and verified gap/merit pairs, without publishing full starting-prime expressions.
- distinguishes FOUND.tsv candidates from independently checked OK results in VERIFIED.tsv.
- summarizes newly checked merit >=25, 30, 40 results per reserved worker-hour.
- saves state, evidence, and records snapshot after every segment in fleet/backups.
- precharges the cumulative core-hour budget to fleet/budget.json, so a crash cannot reset compute reservations.
- respects a fleet/STOP kill switch and a bounded campaign count.

## prerequisites

run on your own Linux/Mac or an appropriately provisioned compute host. use Python 3.10+ and build ./hunter first. the repo needs a valid records.txt. keep the native Hunter control API/firewall isolated: it has no built-in authentication. do not point several Hunter servers at the same state.tsv working directory.

## safe dry run, no compute launched

    cd ~/hunter
    python3 -m unittest -v test_fleet_supervisor.py
    python3 fleet_supervisor.py --dry-run --cores 4 --campaign-hours 1 --max-campaigns 2 --budget-core-hours 8
    python3 fleet_supervisor.py --status

## example bounded approved compute campaign

    cd ~/hunter
    ./build.sh
    python3 fleet_supervisor.py --cores 10 --campaign-hours 5 --max-campaigns 2 --budget-core-hours 100 --checkpoint-minutes 15

this uses one local Hunter server to coordinate 10 native workers. it requires a host with at least 10 logical processors. both segments reserve 100 worker-hours total; the next invocation sees the spent budget and will not automatically restart. this is deliberate, not a loophole for unattended GitHub compute.

to request a graceful stop, create fleet/STOP. remove the file manually before running another explicit budgeted campaign.

## optional 15-minute GitHub issue reporting

export a fine-grained GitHub token with Issues write access in GH_TOKEN and pass --publish. do not commit tokens. the controller creates a single issue and updates its body every checkpoint; failure to publish does not stop the hunt.

## what this does not prove

- unit tests pass, but this is NOT yet tested for a full live hunting cycle.
- independent probable-prime checks are not primality certificates. recheck global records independently.
- worker-hour reservation is a conservative compute budget, NOT measured CPU usage.
- Praetor's existing learner makes arm decisions; this patch does not claim a new high-merit algorithm or any demonstrated merit-30 speedup.
- the Bourgeois spectral/merit-frontier scout remains a separate shadow-mode experiment.

GitHub Actions terms require hosted-runner work to relate to development, testing, deployment, or publication of repository software. do not set up a perpetually relaunching GitHub-hosted research compute farm. use purpose-built or owned compute for ongoing work.
