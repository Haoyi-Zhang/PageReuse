"""Small inert gzip-reader controls; no native execution or timers."""
import gzip
import importlib.util
import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

spec = importlib.util.spec_from_file_location('policy_records', Path(__file__).with_name('check_policies.py'))
records = importlib.util.module_from_spec(spec)
spec.loader.exec_module(records)


class Records(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_plain_gzip_and_transparent_name(self):
        raw = b'\xef\xbb\xbf{"v":1}\r\n{"v":2}\n'
        plain = self.root / 'rows.jsonl'
        plain.write_bytes(raw)
        zipped = self.root / 'rows.jsonl.gz'
        zipped.write_bytes(gzip.compress(raw, mtime=0))
        self.assertEqual(list(records.read_rows(plain)), [{'v': 1}, {'v': 2}])
        self.assertEqual(list(records.read_rows(zipped)), list(records.read_rows(plain)))
        self.assertEqual(records.decoded_identity(zipped), records.decoded_identity(plain))
        plain.unlink()
        self.assertEqual(list(records.read_rows(plain)), [{'v': 1}, {'v': 2}])

    def test_cap_is_decompressed_not_compressed(self):
        raw = json.dumps({'v': 'x' * 4096}).encode() + b'\n'
        zipped = self.root / 'rows.jsonl.gz'
        zipped.write_bytes(gzip.compress(raw, mtime=0))
        self.assertLess(zipped.stat().st_size, 128)
        with self.assertRaisesRegex(ValueError, 'decompressed record bound'):
            list(records.read_rows(zipped, byte_cap=128))
        with self.assertRaisesRegex(ValueError, 'decompressed record bound'):
            records.decoded_identity(zipped, byte_cap=128)

    def test_cumulative_cap_and_exact_limit(self):
        raw = b'{"v":1}\n' * 10
        path = self.root / 'rows.jsonl.gz'
        path.write_bytes(gzip.compress(raw, mtime=0))
        self.assertEqual(len(list(records.read_rows(path, byte_cap=len(raw)))), 10)
        with self.assertRaises(ValueError):
            list(records.read_rows(path, byte_cap=len(raw)-1))

    def test_concatenated_members_preserve_all_rows(self):
        path = self.root / 'rows.jsonl.gz'
        path.write_bytes(gzip.compress(b'{"v":1}\n', mtime=0) + gzip.compress(b'{"v":2}\n', mtime=0))
        self.assertEqual(list(records.read_rows(path)), [{'v': 1}, {'v': 2}])

    def test_truncated_gzip_rejects(self):
        path = self.root / 'rows.jsonl.gz'
        path.write_bytes(gzip.compress(b'{"v":1}\n', mtime=0)[:-5])
        with self.assertRaises((EOFError, gzip.BadGzipFile)):
            records.decoded_identity(path)

    def test_ambiguous_or_nonfinite_json_rejects(self):
        path=self.root/'invalid.jsonl'
        for text in ('{"v":1,"v":2}\n','{"v":NaN}\n','{"v":1e9999}\n'):
            path.write_text(text,encoding='utf-8')
            with self.subTest(text=text), self.assertRaises((ValueError,AssertionError)):
                list(records.read_rows(path))

    def test_counter_identity_is_type_sensitive(self):
        for number in (False,0.0):
            self.assertFalse(records.same({'count':number},{'count':0}))

    def test_source_binding_keeps_current_and_measured_auditors_distinct(self):
        import hashlib
        (self.root/'native').mkdir()
        (self.root/'data').mkdir()
        current=self.root/'native/check_policies.py'
        current.write_bytes(b'current checker')
        old='measured checker'
        context=self.root/'data/measured_policy_checker.json'
        context.write_text(json.dumps({'path':'native/check_policies.py','source':old}))
        with patch.object(records,'ROOT',self.root):
            records.check_source_binding('native/check_policies.py', records.digest(current))
            old_hash=hashlib.sha256(old.encode()).hexdigest().upper()
            records.check_source_binding('native/check_policies.py',old_hash)
            context.write_text(json.dumps({'path':'native/check_policies.py','source':old+' changed'}))
            with self.assertRaisesRegex(ValueError,'measured policy checker binding'):
                records.check_source_binding('native/check_policies.py',old_hash)
            with self.assertRaisesRegex(ValueError,'current source mismatch'):
                records.check_source_binding('native/check_policies.py/../check_policies.py',old_hash)

    def test_timing_summary_preserves_measured_identity_and_all_values(self):
        import hashlib
        timing_spec=importlib.util.spec_from_file_location('timing_records',Path(__file__).with_name('check_policy_timing.py'))
        timing=importlib.util.module_from_spec(timing_spec)
        timing_spec.loader.exec_module(timing)
        (self.root/'data').mkdir()
        old='original timing auditor'
        old_hash=hashlib.sha256(old.encode()).hexdigest().upper()
        fixture=self.root/'data/measured_timing_checker.json'
        fixture.write_text(json.dumps({'path':'native/check_policy_timing.py','source':old}))
        saved={'verifier_sha256':old_hash,'samples':3080}
        current={'verifier_sha256':'CURRENT','samples':3080}
        with patch.object(timing,'ROOT',self.root):
            self.assertTrue(timing.verify_summary(saved,current))
            self.assertFalse(timing.verify_summary(saved,{**current,'samples':3079}))
            fixture.write_text(json.dumps({'path':'native/check_policy_timing.py','source':old+' changed'}))
            with self.assertRaisesRegex(ValueError,'measured timing auditor binding'):
                timing.verify_summary(saved,current)


if __name__ == '__main__':
    unittest.main()
