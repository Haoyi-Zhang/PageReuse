"""Small inert gzip-reader controls; no native execution or timers."""
import gzip
import importlib.util
import json
import tempfile
import unittest
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


if __name__ == '__main__':
    unittest.main()
