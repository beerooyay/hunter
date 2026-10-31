import importlib.util
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("moon", Path(__file__).resolve().parents[1] / "moon.py")
moon = importlib.util.module_from_spec(spec)
spec.loader.exec_module(moon)


class checks(unittest.TestCase):
    def testparse(self):
        text = "7\t-602.1\t20\t-600\n@\t7\t2,8\t3,9\nprobe complete\n"
        row = moon.parse(text)[0]
        self.assertEqual(row["right"], [2, 8])
        self.assertEqual(row["left"], [3, 9])
        self.assertEqual(row["logp"], -602.1)

    def testmissing(self):
        with self.assertRaises(ValueError):
            moon.parse("7\t-2\t20\t-1\nprobe complete\n")
        with self.assertRaises(ValueError):
            moon.parse("7\t-2\t20\t-1\n@\t7\t2,2\t3\nprobe complete\n")
        with self.assertRaises(ValueError):
            moon.parse("7\t-2\t20\t-1\n@\t7\t2\t3\n")

    def testverify(self):
        self.assertTrue(moon.verify(23, 29))
        self.assertFalse(moon.verify(23, 31))
        self.assertFalse(moon.verify(25, 29))

    def testaccounting(self):
        args = moon.argparse.Namespace(seed=50, merit=1, goal=1, seconds=1, keep=1)
        row = dict(m=1, logp=-2, tests=2, rate=0, right=[3], left=[3])
        with tempfile.TemporaryDirectory() as name:
            folder = Path(name)
            (folder / "records.txt").write_text("6 0\n")
            with patch.object(moon.gmpy2, "primorial", return_value=moon.gmpy2.mpz(5460)):
                with patch.object(moon, "call", return_value=[row]):
                    moon.worker(args, folder, time.monotonic() + 5)
            state = moon.json.loads((folder / "summary.json").read_text())
            self.assertEqual(state["records"], 1)
            self.assertEqual(state["targets"], 1)
            self.assertEqual(state["status"], "record goal reached")
            self.assertTrue((folder / "found.tsv").read_text().startswith("6\t"))

    def teststop(self):
        args = moon.argparse.Namespace(seed=50, merit=50, goal=50, seconds=1, keep=1)
        with tempfile.TemporaryDirectory() as name:
            folder = Path(name)
            (folder / "records.txt").write_text("6 1\n")
            (folder / "STOP").touch()
            moon.worker(args, folder, time.monotonic() + 5)
            state = moon.json.loads((folder / "summary.json").read_text())
            self.assertEqual(state["tested"], 0)
            self.assertEqual(state["status"], "budget exhausted or stopped")


if __name__ == "__main__":
    unittest.main()
