"""No hardware or network required: fleet metadata and reporting tests."""
import json
import sqlite3
import tarfile
import hashlib
from pathlib import Path
import tempfile
import unittest
from fleet_supervisor import summarize, backup, atomic_json, github_report, read_ledger
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
            with tarfile.open(archive) as tf:
                self.assertIn("fleet/budget.json",tf.getnames())

    def test_research_wal_backup_is_consistent_and_checksummed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'learning').mkdir()
            db=sqlite3.connect(root/'learning/research.sqlite3')
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE trials(value)');db.execute('INSERT INTO trials VALUES(1)');db.commit()
            db.execute('INSERT INTO trials VALUES(2)') # uncommitted writer must not contaminate backup
            (root/'learning/shared.json').write_text('{"version":1}')
            archive=backup(root,root/'fleet',1,{})
            with tempfile.TemporaryDirectory() as restore:
                with tarfile.open(archive) as tf:tf.extractall(restore,filter='data')
                restore=Path(restore)
                with sqlite3.connect(restore/'learning/research.sqlite3') as restored:
                    self.assertEqual(restored.execute('SELECT * FROM trials').fetchall(),[(1,)])
                manifest=json.loads((restore/'manifest.json').read_text())
                for name,digest in manifest['backup']['files_sha256'].items():
                    self.assertEqual(hashlib.sha256((restore/name).read_bytes()).hexdigest(),digest)
                self.assertFalse(list(restore.rglob('*-wal')))
            db.rollback();db.close()

    def test_late_verification_is_not_a_new_discovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'FOUND.tsv').write_text('156200\t26.4\told\n')
            (root/'VERIFIED.tsv').write_text('156200\t-\told\tOK\n')
            result=summarize(root,{'old'},set())
            self.assertEqual(result['verified_merit_25_new'],0)

    def test_corrupt_budget_never_resets(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'budget.json'
            for value in ('broken','{"reserved_core_hours":-1}','{"reserved_core_hours":NaN}'):
                p.write_text(value)
                with self.assertRaises(RuntimeError):read_ledger(p)

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
