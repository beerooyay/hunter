"""Safety gate for bounded independent hunters and result classification.

    python3 blitz_tests.py            # stdlib-only runner/report checks
    python3 blitz_tests.py --native   # also exercise a staged compiled hunter

Native cases copy the binary into a temporary directory, use a tiny reserved
range, and stop after observing allocation. They never use production state.
"""
from __future__ import annotations
import argparse
import contextlib
import csv
import importlib
import io
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
FLAGS, UNITTEST_ARGS = argparse.ArgumentParser(add_help=False).parse_known_args()
RUN_NATIVE = "--native" in UNITTEST_ARGS
UNITTEST_ARGS = [arg for arg in UNITTEST_ARGS if arg != "--native"]
campaign = importlib.import_module("blitz_campaign")
report = importlib.import_module("blitz_report")

RUN_ID = 44669582169
EXPRESSION = "4466958216814001773*6007#/2310-83194"
GAP = 172180
MERIT = "29.0002"
GAP_LINE = "\t".join([
    "P6007_d2310_L1e9", "4466958216814001773", "2579", ".1", ".2",
    "1", "83194", "88986", str(GAP), MERIT, "33.4567", "1", "2", ".3", "1", "0",
])
FOUND_LINE = f"{GAP}\t{MERIT}\t{EXPRESSION}\tprevious_record_merit=16.2446\t2026-11-21"


def default_env(**changes):
    env = {
        "GITHUB_RUN_ID": str(RUN_ID), "GITHUB_RUN_ATTEMPT": "1",
        "HUNTER_SHARD": "0", "HUNTER_ARM": "6007.2310",
        "HUNTER_LAMBDA_PERCENT": "100", "HUNTER_VARIANT": "baseline",
        "GITHUB_SHA": "0" * 40,
    }
    env.update({key: str(value) for key, value in changes.items()})
    return env


class NamespaceTests(unittest.TestCase):
    def test_declared_campaign_has_one_hundred_fresh_bounded_jobs(self):
        plan = importlib.import_module("blitz_plan").matrix()["include"]
        self.assertEqual(len(plan), 100)
        self.assertEqual({job["shard"] for job in plan}, set(range(100)))
        self.assertEqual(sum(job["variant"] == "baseline" for job in plan), 80)
        self.assertEqual(sum(job["variant"] == "half-cutoff" for job in plan), 20)
        for job in plan:
            with self.subTest(job=job):
                percent = 50 if job["variant"] == "half-cutoff" else 100
                cfg = campaign.make_config(default_env(
                    HUNTER_SHARD=job["shard"], HUNTER_ARM=job["arm"],
                    HUNTER_VARIANT=job["variant"], HUNTER_LAMBDA_PERCENT=percent), cpu_count=4)
                self.assertEqual(cfg["seconds"], 18000)
                self.assertEqual(cfg["lambda_percent"], percent)

    def test_every_supported_shard_and_adjacent_runs_are_disjoint(self):
        ranges = []
        for run in (RUN_ID - 1, RUN_ID, RUN_ID + 1):
            for shard in range(campaign.MAX_SHARD + 1):
                lower, upper = campaign.namespace_bounds(run, shard)
                self.assertGreater(lower, 0)
                self.assertEqual(upper - lower, campaign.SHARD_WIDTH)
                self.assertLessEqual(upper, campaign.UINT64_MAX)
                ranges.append((lower, upper, run, shard))
        for left, right in zip(sorted(ranges), sorted(ranges)[1:]):
            self.assertLessEqual(left[1], right[0], (left, right))
        self.assertEqual(len({campaign.namespace_bounds(RUN_ID, shard) for shard in range(100)}), 100)

    def test_bad_namespace_and_every_retry_are_rejected(self):
        for run, shard, attempt in [
            (0, 0, 1), (-1, 0, 1), (RUN_ID, -1, 1),
            (RUN_ID, campaign.MAX_SHARD + 1, 1),
            (RUN_ID, 0, 0), (RUN_ID, 0, 2), (RUN_ID, 0, 9),
            (2**64, 0, 1),
        ]:
            with self.subTest(run=run, shard=shard, attempt=attempt):
                with self.assertRaises((ValueError, OverflowError)):
                    campaign.namespace_bounds(run, shard, attempt)

    def test_word_size_boundary(self):
        largest = (campaign.UINT64_MAX - campaign.SHARD_WIDTH - 1) // campaign.RUN_STRIDE
        lower, upper = campaign.namespace_bounds(largest, 0)
        self.assertLessEqual(upper, campaign.UINT64_MAX)
        with self.assertRaises((ValueError, OverflowError)):
            campaign.namespace_bounds(largest + 1, 0)

    def test_config_validation(self):
        cfg = campaign.make_config(default_env(), cpu_count=4)
        self.assertEqual(cfg["run_id"], RUN_ID)
        self.assertEqual(cfg["shard"], 0)
        self.assertEqual(cfg["cores"], 4)
        self.assertEqual(cfg["lambda_percent"], 100)
        self.assertEqual((cfg["base"], cfg["exclusive_end"]), campaign.namespace_bounds(RUN_ID, 0))
        json.dumps(cfg)
        for change in [
            {"GITHUB_RUN_ATTEMPT": "2"}, {"HUNTER_SHARD": "256"},
            {"GITHUB_RUN_ID": "0"}, {"HUNTER_VARIANT": "unknown"},
            {"HUNTER_SECONDS": "18001"}, {"HUNTER_CORES": "5"},
            {"HUNTER_LAMBDA_PERCENT": "0"}, {"HUNTER_LAMBDA_PERCENT": "101"},
            {"HUNTER_LAMBDA_PERCENT": "50"},
            {"HUNTER_ARM": "bogus"},
        ]:
            with self.subTest(change=change):
                with self.assertRaises((ValueError, OverflowError)):
                    campaign.make_config(default_env(**change), cpu_count=4)
        # An inherited raw override cannot silently change the declared lane.
        with self.assertRaises(ValueError):
            campaign.make_config(default_env(HUNTER_VARIANT="half-cutoff", HUNTER_LAMBDA_PERCENT=100), cpu_count=4)

    def test_template_only_resets_multiplier_cursors(self):
        template = (ROOT / "cloud-state-template.tsv").read_text()
        rendered = campaign.render_state(template, 1234567)
        before = [line.split("\t") for line in template.splitlines() if line.startswith("P")]
        after = [line.split("\t") for line in rendered.splitlines() if line.startswith("P")]
        self.assertEqual(len(before), len(after))
        self.assertGreater(len(after), 0)
        for old, new in zip(before, after):
            self.assertEqual(new[4], "1234567")
            self.assertEqual(old[:4] + old[5:], new[:4] + new[5:])


class StatusAndCleanupTests(unittest.TestCase):
    def test_existing_results_are_rejected_before_launch_or_state_write(self):
        config = campaign.make_config(default_env(), cpu_count=4)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            (path / "FOUND.tsv").write_text(FOUND_LINE + "\n")
            with self.assertRaises(ValueError):
                campaign.run_campaign(config, root=path)
            self.assertFalse((path / "state.tsv").exists())
            self.assertFalse((path / "blitz-manifest.json").exists())

    def status(self, config):
        return {
            "engine": "praetor", "running": True, "stopping": False,
            "range_exhausted": False, "now": 100, "started": 100, "ends": 18100,
            "cores": config["cores"], "m_end": str(config["exclusive_end"]),
            "lambda_percent": config["lambda_percent"], "learned_lambda": .25,
            "effective_lambda": .25, "tasks": {"verifying": 0},
            "arms": [{"P": config["P"], "d": config["d"], "on": True}],
            "workers": [{"P": config["P"], "d": config["d"], "m0": config["base"], "M": 20}],
        }

    def test_status_rejects_missing_cap_wrong_lane_and_escaped_worker(self):
        config = campaign.make_config(default_env(), cpu_count=4)
        campaign.validate_status(self.status(config), config, expect_running=True)
        cases = []
        for field, value in [("m_end", "0"), ("lambda_percent", 50), ("cores", 8), ("running", False)]:
            state = self.status(config)
            state[field] = value
            cases.append((field, state))
        for m, count in [(config["base"] - 1, 20), (config["exclusive_end"] - 1, 2)]:
            state = self.status(config)
            state["workers"][0].update(m0=m, M=count)
            cases.append(("escaped worker", state))
        state = self.status(config)
        state["arms"].append({"P": 8009, "d": 210, "on": True})
        cases.append(("unassigned active family", state))
        for label, state in cases:
            with self.subTest(label=label):
                with self.assertRaises((RuntimeError, ValueError)):
                    campaign.validate_status(state, config, expect_running=True)
        exhausted = self.status(config)
        exhausted.update(running=False, stopping=True, range_exhausted=True, workers=[])
        campaign.validate_status(exhausted, config, expect_running=True)

    def test_owned_group_cleanup_preserves_unrelated_process(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            args = [sys.executable, "-c", "import time; time.sleep(30)"]
            decoy = subprocess.Popen(args, start_new_session=True)
            owned = campaign.spawn_owned(args, path, path / "owned.log")
            try:
                campaign.terminate_owned_group(owned, timeout=1)
                self.assertIsNotNone(owned.poll())
                self.assertIsNone(decoy.poll(), "cleanup signalled an unrelated process")
            finally:
                for process in (owned, decoy):
                    with contextlib.suppress(ProcessLookupError):
                        os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)

    def test_cleanup_refuses_a_process_in_the_test_runners_group(self):
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        try:
            with self.assertRaises(RuntimeError):
                campaign.terminate_owned_group(child, timeout=.1)
            self.assertIsNone(child.poll())
        finally:
            child.kill()
            child.wait(timeout=5)


class CandidateParsingTests(unittest.TestCase):
    def test_actual_merit_survives_zero_found_and_higher_old_merit(self):
        row = report.parse_gap_line(GAP_LINE, source="gaps.tsv", line_number=7)
        self.assertIsNotNone(row)
        self.assertEqual(row["gap"], GAP)
        self.assertEqual(float(row["merit"]), float(MERIT))
        self.assertEqual(row["expression"], EXPRESSION)
        self.assertEqual(row["P"], 6007)
        self.assertEqual(row["d"], 2310)
        self.assertEqual(row["left"], 83194)

    def test_partial_and_nonfinite_rows_do_not_become_candidates(self):
        for column, value in [(5, "0"), (8, "0")]:
            fields = GAP_LINE.split("\t")
            fields[column] = value
            with self.subTest(column=column, value=value):
                self.assertIsNone(report.parse_gap_line("\t".join(fields)))
        for column, value in [(9, "nan"), (9, "inf"), (9, "-1"), (7, "88987")]:
            fields = GAP_LINE.split("\t")
            fields[column] = value
            with self.subTest(column=column, value=value):
                with self.assertRaises(ValueError):
                    report.parse_gap_line("\t".join(fields))
        for line in ["", "# configured target merit 40"]:
            with self.subTest(line=line):
                self.assertIsNone(report.parse_gap_line(line))
        for line in ["checkpoint 0 4", "T\t1\t40", "P6007_d2310_L1e9\t1"]:
            with self.subTest(line=line):
                with self.assertRaises(ValueError):
                    report.parse_gap_line(line)

    def test_found_and_verified_use_exact_candidate_identity(self):
        row = report.parse_found_line(FOUND_LINE)
        self.assertIsNotNone(row)
        self.assertEqual((row["gap"], row["expression"]), (GAP, EXPRESSION))
        verified = report.parse_verified_line(f"{GAP}\t-\t{EXPRESSION}\tOK")
        self.assertIsNotNone(verified)
        self.assertEqual((verified["gap"], verified["expression"]), (GAP, EXPRESSION))
        with self.assertRaises(ValueError):
            report.parse_verified_line(f"{GAP}\t-\t{EXPRESSION}\tPENDING")


class ReportClassificationTests(unittest.TestCase):
    def make_job(self, path, *, found=True, raw=True, verification=""):
        path.mkdir(parents=True, exist_ok=True)
        if found:
            (path / "FOUND.tsv").write_text(FOUND_LINE + "\n")
        if raw:
            (path / "gaps.tsv").write_text(GAP_LINE + "\n")
        if verification:
            (path / "VERIFIED.tsv").write_text(verification)
        return path

    def test_zero_found_high_merit_is_visible_but_pending(self):
        with tempfile.TemporaryDirectory() as temp:
            path = self.make_job(Path(temp), found=False)
            result = report.write_job_report(path)
            self.assertEqual(result["metrics"]["found"], 0)
            self.assertEqual(result["metrics"]["high_merit_raw"], 1)
            self.assertEqual(result["metrics"]["tails"]["29"], 1)
            self.assertEqual(float(result["metrics"]["best_actual_merit"]), 29.0002)
            self.assertEqual(result["candidates"][0]["verification_status"], "PENDING")
            self.assertIn(EXPRESSION, (path / "HIGH_MERIT.tsv").read_text())
            self.assertIn(EXPRESSION, (path / "PENDING.tsv").read_text())
            self.assertNotIn(EXPRESSION, (path / "READY.tsv").read_text())
            self.assertEqual((path / "READY.txt").read_text(), "")

    def test_verified_nonrecord_tail_requires_record_comparison_before_ready(self):
        with tempfile.TemporaryDirectory() as temp:
            path = self.make_job(Path(temp), found=False,
                                 verification=f"{GAP}\t-\t{EXPRESSION}\tOK\n")
            result = report.write_job_report(path)
            self.assertEqual(result["candidates"][0]["verification_status"], "OK")
            self.assertFalse(result["candidates"][0]["reported_found"])
            self.assertIn(EXPRESSION, (path / "HIGH_MERIT.tsv").read_text())
            self.assertIn(EXPRESSION, (path / "VERIFIED_HIGH_MERIT.tsv").read_text())
            self.assertNotIn(EXPRESSION, (path / "READY.tsv").read_text())
            self.assertEqual((path / "READY.txt").read_text(), "")

    def test_tail_monitor_announces_complete_actual_tail_once(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            monitor = campaign.TailMonitor(path)
            output = io.StringIO()
            split = len(GAP_LINE) // 2
            with contextlib.redirect_stdout(output):
                (path / "gaps.tsv").write_text(GAP_LINE[:split])
                monitor.poll()
                self.assertEqual(output.getvalue(), "")
                with (path / "gaps.tsv").open("a") as handle:
                    handle.write(GAP_LINE[split:] + "\n")
                monitor.poll()
                with (path / "gaps.tsv").open("a") as handle:
                    handle.write(GAP_LINE + "\n")
                monitor.poll()
            self.assertEqual(output.getvalue().count("HIGH_MERIT"), 1)
            self.assertIn("status=PENDING", output.getvalue())
            self.assertIn(MERIT, output.getvalue())
            self.assertNotIn("33.4567", output.getvalue())

    def test_only_matching_ok_is_ready_conflicts_and_failures_hold(self):
        checks = [
            ("", "PENDING"),
            (f"{GAP + 2}\t-\t{EXPRESSION}\tOK\n", "PENDING"),
            (f"{GAP}\t-\t{EXPRESSION.replace('-83194', '-83196')}\tOK\n", "PENDING"),
            (f"{GAP}\t-\t{EXPRESSION}\tOK\n", "OK"),
            (f"{GAP}\t-\t{EXPRESSION}\tFAILED\n", "FAILED"),
            (f"{GAP}\t-\t{EXPRESSION}\tOK\n{GAP}\t-\t{EXPRESSION}\tFAILED\n", "CONFLICT"),
        ]
        for verification, expected in checks:
            with self.subTest(expected=expected, verification=verification), tempfile.TemporaryDirectory() as temp:
                path = self.make_job(Path(temp), verification=verification)
                raw_before = (path / "gaps.tsv").read_bytes()
                found_before = (path / "FOUND.tsv").read_bytes()
                result = report.write_job_report(path)
                self.assertEqual(len(result["candidates"]), 1)
                self.assertEqual(result["candidates"][0]["verification_status"], expected)
                self.assertEqual(EXPRESSION in (path / "READY.txt").read_text(), expected == "OK")
                self.assertEqual((path / "gaps.tsv").read_bytes(), raw_before)
                self.assertEqual((path / "FOUND.tsv").read_bytes(), found_before)

    def test_torn_or_malformed_final_line_is_held_and_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            path = self.make_job(Path(temp))
            (path / "VERIFIED.tsv").write_text(f"{GAP}\t-\t{EXPRESSION}\tOK")
            with (path / "gaps.tsv").open("a") as handle:
                handle.write("checkpoint configured merit 40\n")
            result = report.write_job_report(path)
            self.assertEqual(result["candidates"][0]["verification_status"], "PENDING")
            self.assertEqual(result["error_count"], 2)
            self.assertEqual((path / "READY.txt").read_text(), "")

    def test_aggregate_deduplicates_and_preserves_cross_artifact_conflict(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            incoming, outgoing = root / "incoming", root / "outgoing"
            for name in ("a", "b"):
                self.make_job(incoming / name, verification=f"{GAP}\t-\t{EXPRESSION}\tOK\n")
            first = report.aggregate(incoming, outgoing)
            self.assertEqual(first["unique_candidates"], 1)
            self.assertEqual(first["candidate_counts"]["OK"], 1)
            self.assertEqual((outgoing / "READY.txt").read_text().count(EXPRESSION), 1)
            self.make_job(incoming / "c", verification=f"{GAP}\t-\t{EXPRESSION}\tFAILED\n")
            second = report.aggregate(incoming, outgoing)
            self.assertEqual(second["unique_candidates"], 1)
            self.assertEqual(second["candidate_counts"]["CONFLICT"], 1)
            self.assertEqual((outgoing / "READY.txt").read_text(), "")


class StagedNative:
    """Dedicated process group and copied executable; safe to kill in finally."""
    def __init__(self, *, percent=100, cold=False, width=1000, dry=False):
        self.percent = percent
        self.cold = cold
        self.width = width
        self.dry = dry
        self.base = 10000001

    def __enter__(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hunter-native-gate-")
        self.path = Path(self.temp.name)
        shutil.copy2(ROOT / "hunter", self.path / "hunter")
        shutil.copy2(ROOT / "records.txt", self.path / "records.txt")
        row = next(line.split("\t") for line in (ROOT / "cloud-state-template.tsv").read_text().splitlines()
                   if line.startswith("P4001_d210_L1e9\t"))
        row[4] = str(self.base)                  # next_m
        row[5] = str(1 << 40)                   # prior
        for field in (5, 6, 7, 9, 10, 11, 12, 13, 17, 18, 19, 20, 21, 22, 65):
            row[field + 1] = "0"
        for field in range(25, 65):
            row[field + 1] = "0"
        row[9] = "0" if self.cold else "1"     # tested
        row[15] = str(10**9)                    # ns per raw multiplier
        row[16] = "0" if self.dry else "2"     # priced
        state_rows = [row]
        if self.dry:
            # A second priced arm supplies a nonzero learned cutoff while the
            # first arm's dry pricing job is chosen. Scaling that dry job
            # would change the learned model itself.
            anchor = next(line.split("\t") for line in (ROOT / "cloud-state-template.tsv").read_text().splitlines()
                          if line.startswith("P4001_d2310_L1e9\t"))
            anchor[4], anchor[5], anchor[9], anchor[16] = str(self.base), str(1 << 40), "1", "2"
            state_rows.append(anchor)
        (self.path / "state.tsv").write_text("".join("\t".join(fields) + "\n" for fields in state_rows))
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            self.port = sock.getsockname()[1]
        self.url = f"http://127.0.0.1:{self.port}"
        env = dict(os.environ)
        for key in ("HUNT_DRY", "HUNT_MASK_REFERENCE", "HUNTER_GPU"):
            env.pop(key, None)
        env.update(HUNTER_NO_OPEN="1", HUNTER_M_END=str(self.base + self.width),
                   HUNTER_LAMBDA_PERCENT=str(self.percent), HUNTER_PORT=str(self.port))
        self.log = open(self.path / "server.log", "wb")
        self.proc = subprocess.Popen([str(self.path / "hunter"), "serve", str(self.port)],
            cwd=self.path, env=env, stdout=self.log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                if self.proc.poll() is not None:
                    raise AssertionError("staged server exited: " + (self.path / "server.log").read_text())
                try:
                    self.request("/api/status")
                    return self
                except (OSError, ValueError):
                    time.sleep(.05)
            raise AssertionError("staged server startup timed out")
        except BaseException as error:
            self.__exit__(type(error), error, error.__traceback__)
            raise

    def request(self, path, **data):
        body = urllib.parse.urlencode(data).encode() if data else None
        with urllib.request.urlopen(self.url + path, data=body, timeout=3) as response:
            return json.load(response)

    def start(self):
        arms = "4001.210,4001.2310" if self.dry else "4001.210"
        answer = self.request("/api/start", cores=1, hours=.02, job=20, gpu=0, arms=arms)
        if not answer.get("ok"):
            raise AssertionError(answer)

    def reservations(self):
        path = self.path / "job-reservations.tsv"
        if not path.exists():
            return []
        lines = path.read_text().splitlines()
        if not lines:
            return []
        header = ["epoch", "core", "arm", "m0", "M", "dry", "cold", "lambda_percent",
                  "learned_lambda_per_core_hour", "effective_lambda_per_core_hour", "end_exclusive"]
        if lines[0].startswith("#"):
            lines = lines[1:]
        return list(csv.DictReader(lines, fieldnames=header, delimiter="\t"))

    def wait_for_reservation(self):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            rows = self.reservations()
            if rows:
                return rows[0]
            if self.proc.poll() is not None:
                break
            time.sleep(.03)
        raise AssertionError("no reservation: " + (self.path / "server.log").read_text())

    def stop(self):
        self.request("/api/stop", now=1)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            status = self.request("/api/status")
            if not status.get("workers") and not status.get("running"):
                return status
            time.sleep(.05)
        raise AssertionError("staged worker failed to stop")

    def __exit__(self, kind, value, traceback):
        try:
            if hasattr(self, "proc"):
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(self.proc.pid, signal.SIGTERM)
                try:
                    self.proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    with contextlib.suppress(ProcessLookupError):
                        os.killpg(self.proc.pid, signal.SIGKILL)
                    self.proc.wait(timeout=5)
        finally:
            if hasattr(self, "log"):
                self.log.close()
            if kind is not None:
                for filename in ("server.log", "hunt.log", "job-reservations.tsv"):
                    path = self.path / filename
                    if path.exists():
                        print(f"\n--- isolated native diagnostic {filename} ---\n{path.read_text()[-12000:]}", flush=True)
            self.temp.cleanup()


@unittest.skipUnless(RUN_NATIVE, "pass --native after building ./hunter")
class NativeAllocationTests(unittest.TestCase):
    def test_two_second_full_wrapper_reaches_final_report_and_cleans_up(self):
        with tempfile.TemporaryDirectory(prefix="hunter-wrapper-gate-") as temp:
            path = Path(temp)
            for name in ("hunter", "cloud-state-template.tsv", "records.txt"):
                shutil.copy2(ROOT / name, path / name)
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            config = campaign.make_config(default_env(
                HUNTER_SECONDS=2, HUNTER_CORES=1, HUNTER_PORT=port,
                GITHUB_SHA=os.environ.get("GITHUB_SHA", "0" * 40)), cpu_count=4)
            plan = importlib.import_module("blitz_plan")
            build = {
                "schema_version": 1, "compiler_sha": plan.COMPILER_SHA,
                "records_sha256": report.sha256(path / "records.txt"),
                "hunter_binary_sha256": report.sha256(path / "hunter"),
                "hunter_sha": config["sha"], "matrix": plan.matrix(),
            }
            (path / "build-manifest.json").write_text(json.dumps(build) + "\n")
            spawned = []
            original_spawn = campaign.spawn_owned

            def capture_spawn(*args, **kwargs):
                process = original_spawn(*args, **kwargs)
                spawned.append(process)
                return process

            output = io.StringIO()
            try:
                with contextlib.redirect_stdout(output), mock.patch.object(campaign, "DRAIN_SECONDS", 0), \
                     mock.patch.object(campaign, "VERIFY_SECONDS", 0), \
                     mock.patch.object(campaign, "spawn_owned", side_effect=capture_spawn):
                    result = campaign.run_campaign(config, root=path)
                manifest = json.loads((path / "blitz-manifest.json").read_text())
                self.assertEqual(manifest["outcome"], "completed")
                self.assertEqual(result["error_count"], 0)
                self.assertTrue((path / "blitz-summary.json").exists())
                self.assertTrue((path / "READY.txt").exists())
                self.assertTrue((path / "PENDING.tsv").exists())
                self.assertTrue(spawned)
                self.assertTrue(all(process.poll() is not None for process in spawned))
                with socket.socket() as sock:
                    self.assertNotEqual(sock.connect_ex(("127.0.0.1", port)), 0)
            except BaseException:
                print("\n--- isolated full-wrapper diagnostics ---\n" + output.getvalue(), flush=True)
                for name in ("native-server.log", "hunt.log", "blitz-manifest.json"):
                    if (path / name).exists():
                        print(name + "\n" + (path / name).read_text()[-12000:], flush=True)
                raise
            finally:
                for process in spawned:
                    campaign.terminate_owned_group(process, timeout=1)

    def test_half_cutoff_preserves_raw_learning_and_applies_to_worker(self):
        learned = []
        effective = []
        for percent, expected in [(100, .25), (50, .125)]:
            with self.subTest(percent=percent), StagedNative(percent=percent) as staged:
                staged.start()
                reservation = staged.wait_for_reservation()
                status = staged.request("/api/status")
                learned.append(float(status["learned_lambda"]))
                effective.append(float(status["effective_lambda"]))
                self.assertAlmostEqual(learned[-1], .25, places=5)
                self.assertAlmostEqual(effective[-1], expected, places=5)
                self.assertAlmostEqual(float(reservation["learned_lambda_per_core_hour"]), .25, places=5)
                self.assertAlmostEqual(float(reservation["effective_lambda_per_core_hour"]), expected, places=5)
                self.assertEqual(int(reservation["lambda_percent"]), percent)
                self.assertEqual(int(reservation["cold"]), 0)
                self.assertEqual(int(reservation["dry"]), 0)
                staged.stop()
        self.assertEqual(learned[0], learned[1])
        self.assertAlmostEqual(effective[0], 2 * effective[1], places=5)

    def test_cold_allocation_caps_at_boundary_and_exhausts(self):
        with StagedNative(percent=50, cold=True, width=6) as staged:
            staged.start()
            reservation = staged.wait_for_reservation()
            self.assertEqual(int(reservation["m0"]), staged.base)
            self.assertEqual(int(reservation["M"]), 6)
            self.assertEqual(int(reservation["end_exclusive"]), staged.base + 6)
            self.assertEqual(int(reservation["cold"]), 1)
            self.assertEqual(float(reservation["effective_lambda_per_core_hour"]), 0)
            for worker in staged.request("/api/status")["workers"]:
                self.assertLessEqual(int(worker["m0"]) + int(worker["M"]), staged.base + 6)
            staged.stop()
            row = next(line.split("\t") for line in (staged.path / "state.tsv").read_text().splitlines()
                       if line.startswith("P4001_d210_L1e9\t"))
            self.assertEqual(int(row[4]), staged.base + 6)
            count = len(staged.reservations())
            staged.start()
            time.sleep(.35)  # scheduler has a 200 ms tick
            status = staged.request("/api/status")
            self.assertFalse(status.get("workers"), status)
            self.assertEqual(len(staged.reservations()), count)
            self.assertTrue(status["range_exhausted"], status)
            self.assertIn("exhaust", (staged.path / "hunt.log").read_text().lower())

    def test_dry_pricing_keeps_unscaled_cutoff(self):
        with StagedNative(percent=50, dry=True) as staged:
            staged.start()
            reservation = staged.wait_for_reservation()
            self.assertEqual(int(reservation["dry"]), 1)
            self.assertEqual(int(reservation["cold"]), 0)
            self.assertAlmostEqual(float(reservation["learned_lambda_per_core_hour"]), .25, places=5)
            self.assertAlmostEqual(float(reservation["effective_lambda_per_core_hour"]), .25, places=5)
            staged.stop()


if __name__ == "__main__":
    unittest.main(argv=[__file__, *UNITTEST_ARGS], verbosity=2)
