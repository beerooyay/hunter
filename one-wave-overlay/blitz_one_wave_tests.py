import collections
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import blitz_plan
from blitz_one_wave import coverage, start


class OneWaveTests(unittest.TestCase):
    def test_exact_mix_and_original_default(self):
        old = blitz_plan.matrix()
        self.assertEqual(old, blitz_plan.matrix(100))
        small = blitz_plan.matrix(20)
        self.assertEqual(small["include"], old["include"][:20])
        self.assertEqual(collections.Counter(r["arm"] for r in small["include"]),
                         {"6007.2310": 8, "8009.2310": 8, "6007.210": 4})
        self.assertEqual(collections.Counter(r["variant"] for r in small["include"]),
                         {"baseline": 16, "half-cutoff": 4})
        with self.assertRaises(ValueError):
            blitz_plan.matrix(21)

    def test_cli_matrix_equals_manifest_without_live_fetch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "blitz").mkdir()
            (root / "blitz/known-results.tsv").touch()
            records = root / "fixture.txt"
            records.write_text("".join(f"{i} 20.0000 fixture\n" for i in range(1, 100_001)))
            with patch.object(blitz_plan, "ROOT", root):
                manifest = blitz_plan.prepare(records, 20)
        output = subprocess.check_output([sys.executable, "blitz_plan.py", "--matrix", "--shards", "20"])
        self.assertEqual(manifest["matrix"], json.loads(output))
        self.assertEqual(manifest["search_seconds"], 18_000)

    def test_kickoff_wait_and_late_admission(self):
        states = iter([65, 90])
        slept = []
        self.assertTrue(start(90, clock=lambda: next(states), sleep=slept.append)["admitted"])
        self.assertEqual(slept, [25])
        self.assertTrue(start(90, clock=lambda: 105)["admitted"])
        self.assertFalse(start(90, clock=lambda: 105.01)["admitted"])
        with self.assertRaises(ValueError):
            start(0)

    def fixture(self):
        timestamp = datetime.fromtimestamp(95, timezone.utc).isoformat()
        return [{"manifest": dict(r, shard=str(r["shard"]), run_id="123", outcome="completed",
                                   stop_reason="configured hunt deadline", hunt_seconds_requested=18_000,
                                   hunt_started_at=timestamp)} for r in blitz_plan.matrix(20)["include"]]

    def test_complete_coverage_and_late_native_start(self):
        records = self.fixture()
        self.assertTrue(coverage(records, "123", 90)["complete"])
        records[0]["manifest"]["hunt_started_at"] = datetime.fromtimestamp(121, timezone.utc).isoformat()
        c = coverage(records, "123", 90)
        self.assertFalse(c["complete"])
        self.assertEqual(c["late_or_missing_native_start_shards"], [0])

    def test_incomplete_wrong_run_duplicate_and_short_duration(self):
        records = self.fixture()
        records[0]["manifest"]["hunt_seconds_requested"] = 2
        records[1]["manifest"]["run_id"] = "122"
        c = coverage(records[:-1] + [records[2]], "123", 90)
        self.assertFalse(c["complete"])
        self.assertEqual(c["missing_shards"], [1, 19])
        self.assertEqual(c["not_full_duration_shards"], [0])
        self.assertEqual(c["duplicate_shards"], [2])
        self.assertEqual(c["foreign_or_malformed"], 1)


if __name__ == "__main__":
    unittest.main()
