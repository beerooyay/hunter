"""No hardware or network required: fleet metadata and reporting tests."""
import json
from pathlib import Path
import tempfile
import unittest
from fleet_supervisor import summarize, backup, atomic_json, github_report
from unittest.mock import patch

class FleetTests(unittest.TestCase):
    def test_found_verify_and_no_expression_in_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "FOUND.tsv").write_text(
                "156200\t26.4157\t14589341*6007#/210-103794\told=10\n"
                "210786\t26.7089\tM*P#/210-a\nbad\n")
            (p / "VERIFIED.tsv").write_text(
                "156200\t-\t14589341*6007#/210-103794\tOK\n"
                "210786\t-\tM*P#/210-a\tFAILED\n")
            result = summarize(p)
            self.assertEqual(result["found_total"], 2)
            self.assertEqual(result["independently_verified_total"], 1)
            self.assertEqual(result["verified_merit_25_total"], 1)
            self.assertEqual(result["verified_merit_25_new"], 1)
            self.assertEqual(result["top_verified"][0]["merit"], 26.4157)
            self.assertNotIn("6007#", json.dumps(result))

    def test_preexisting_verified_not_new(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "FOUND.tsv").write_text("156200\t26.4157\texpr\n")
            (p / "VERIFIED.tsv").write_text("156200\t-\texpr\tOK\n")
            self.assertEqual(
                summarize(p, {"expr"}, {"expr"})["independently_verified_new"], 0)

    def test_atomic_and_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            atomic_json(p / "fleet" / "budget.json", {"reserved_core_hours": 5})
            self.assertEqual(
                json.loads((p / "fleet" / "budget.json").read_text())["reserved_core_hours"], 5)
            (p / "state.tsv").write_text("state")
            archive = backup(p, p / "fleet", 1, {"example": True})
            self.assertTrue(archive.exists())

    def test_publish_opt_in(self):
        with patch("fleet_supervisor.urllib.request.urlopen") as opener:
            opener.return_value.__enter__.return_value.read.return_value = b'{"number":14}'
            payload = {
                "top_verified": [], "found_total": 0, "found_new": 0,
                "independently_verified_total": 0, "independently_verified_new": 0,
                "verified_merit_25_total": 0, "verified_merit_30_total": 0,
                "verified_merit_40_total": 0, "verified_merit_25_new": 0,
                "verified_merit_30_new": 0, "verified_merit_40_new": 0}
            result = github_report(
                "beerooyay/hunter", "TOKEN", None, payload,
                {"campaign": 1, "cores": 10, "phase": "searching",
                 "budget_reserved": 50, "budget_max": 100}, True)
            self.assertEqual(result, 14)
            req = opener.call_args.args[0]
            self.assertEqual(req.method, "POST")

if __name__ == "__main__":
    unittest.main()
