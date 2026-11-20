import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import portfolio as p


class PortfolioTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_ten_slots(self):
        self.assertEqual(p.split_slots(10), (7, 2, 1))

    def test_small_and_large_splits(self):
        self.assertEqual(p.split_slots(3), (1, 1, 1))
        self.assertEqual(p.split_slots(20), (14, 4, 2))
        for n in range(3, 65):
            self.assertEqual(sum(p.split_slots(n)), n)
            self.assertTrue(all(v > 0 for v in p.split_slots(n)))

    def test_slot_bounds(self):
        for n in (0, 2, 65):
            with self.assertRaises(ValueError):
                p.split_slots(n)

    def test_records_deduplicate(self):
        self.assertEqual(p.parse_records('# comment\n100 20.5 name\n100 19\n102 21\n'),
                         {100: 20.5, 102: 21.})

    def test_records_bad_values(self):
        for text in ('100 nan', '100 inf', '100 -3', '100', '<html>oops</html>'):
            with self.assertRaises(ValueError):
                p.parse_records(text)

    def test_short_snapshot_rejected(self):
        with self.assertRaises(ValueError):
            p.parse_records('100 20', minimum=2)

    def test_atomic_replace(self):
        path = self.root / 'nested/status.json'
        p.save(path, {'a': 1})
        p.save(path, {'a': 2})
        self.assertEqual(p.load(path), {'a': 2})
        self.assertEqual(len(list(path.parent.iterdir())), 1)

    def test_state_only_initialized_once(self):
        template = self.root / 'template.tsv'
        template.write_text('a\tb\tc\td\t99\tf\n')
        state = self.root / 'state.tsv'
        self.assertTrue(p.initialize_native(state, template, 12345))
        self.assertEqual(state.read_text(), 'a\tb\tc\td\t12345\tf\n')
        self.assertFalse(p.initialize_native(state, template, 67890))
        self.assertIn('12345', state.read_text())

    def test_bad_reservation(self):
        template = self.root / 'template.tsv'
        template.write_text('a\tb\tc\td\t99\tf\n')
        with self.assertRaises(ValueError):
            p.initialize_native(self.root/'state.tsv', template, 2**64)

    def test_verified_requires_gap_and_expression(self):
        (self.root/'FOUND.tsv').write_text('100\t20\texpr-a\n102\t21\texpr-b\n104\t22\texpr-c\n')
        (self.root/'VERIFIED.tsv').write_text('100\t-\texpr-a\tOK\n100\t-\texpr-b\tOK\n104\t-\texpr-c\tFAILED\n')
        self.assertEqual(list(p.native_verified(self.root)), [(100,20.,'expr-a')])
        self.assertEqual([x['gap'] for x in p.pending_native(self.root)], [102])

    def test_merge_never_promotes_pending(self):
        volume = self.root/'volume'
        volume.mkdir()
        (volume/'FOUND.tsv').write_text('100\t22\tx\n102\t40\ty\n')
        (volume/'VERIFIED.tsv').write_text('100\t-\tx\tOK\n')
        p.save(self.root/'verification/a.json', {'gap': 106,'merit':31,'start':'101','status':'pending'})
        p.save(self.root/'verification/b.json', {'gap': 108,'merit':32,'start':'103','status':'ok'})
        result = p.publish_records(self.root, {100:20.,102:18.,104:45.}, [volume])
        self.assertEqual(result, {100:22.,102:18.,104:45.,108:32.})

    def test_hosted_production_guard(self):
        with mock.patch.dict(os.environ, {'GITHUB_ACTIONS':'true','RUNNER_ENVIRONMENT':'github-hosted'}):
            with self.assertRaises(RuntimeError):
                p.check_host(10)

    def test_cpu_guard(self):
        with mock.patch.dict(os.environ, {'GITHUB_ACTIONS':''}), mock.patch('os.cpu_count', return_value=4):
            with self.assertRaises(RuntimeError):
                p.check_host(10)

    def test_timeout_retains_pending(self):
        path = self.root/'candidate.json'
        p.save(path, {'status':'pending'})
        with mock.patch('subprocess.run', side_effect=subprocess.TimeoutExpired('verify', .01)):
            with self.assertRaises(subprocess.TimeoutExpired):
                p.verify_bounded(path, .01)
        self.assertEqual(p.load(path)['status'], 'pending')

    def test_known_verification_not_repeated(self):
        path = self.root/'candidate.json'
        p.save(path, {'status':'ok'})
        with mock.patch('subprocess.run') as run:
            self.assertTrue(p.verify_bounded(path, 1))
            run.assert_not_called()

    def test_environment_excludes_stale_mode(self):
        with mock.patch.dict(os.environ, {'HUNT_DRY':'1','HUNTER_GPU':'1'}):
            self.assertNotIn('HUNT_DRY', p.clean_env())
            self.assertNotIn('HUNTER_GPU', p.clean_env())

    @unittest.skipUnless(importlib.util.find_spec('gmpy2'), 'gmpy2 only available in native CI/runtime')
    def test_queue_prime_gap_and_internal_prime(self):
        import gmpy2
        path = p.queue_candidate(self.root, gmpy2.mpz(23), gmpy2.mpz(29))
        self.assertEqual(p.load(path)['status'], 'pending')
        self.assertTrue(p.verify_file(path))
        self.assertEqual(p.load(path)['status'], 'ok')
        bad = p.queue_candidate(self.root, gmpy2.mpz(23), gmpy2.mpz(31))
        self.assertFalse(p.verify_file(bad))
        self.assertEqual(p.load(bad)['status'], 'failed')


if __name__ == '__main__':
    unittest.main()
