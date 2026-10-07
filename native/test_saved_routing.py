"""Portable source-routing controls; inert fixture bytes, no native execution."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import check_saved


NAMES = ("allocator.cpp", "NativeBridge.cs", "bounded.ps1", "run.ps1",
         "check_native.py", "summarize_native.py", "protocol.json")


class SavedRouting(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="p054-routing-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.protocol = {"panel": ["owned-fixture"], "pairs_per_case": 11}
        self.data = {name: ("inert measured fixture: " + name).encode() for name in NAMES}
        self.data["protocol.json"] = json.dumps(self.protocol).encode()
        for name, data in self.data.items():
            (self.root / name).write_bytes(data)
        self.env = {"source_sha256": {name: hashlib.sha256(data).hexdigest().upper()
                                     for name, data in self.data.items()}}

    def test_all_seven_bindings_and_selected_protocol(self):
        self.assertEqual(check_saved.measured_protocol(self.env, self.root), self.protocol)

    def test_each_changed_source_rejects(self):
        for name in NAMES:
            with self.subTest(name=name):
                path = self.root / name
                path.write_bytes(self.data[name] + b"changed")
                with self.assertRaises(AssertionError):
                    check_saved.measured_protocol(self.env, self.root)
                path.write_bytes(self.data[name])

    def test_each_missing_source_rejects(self):
        # Move one small owned fixture, not deletion of any supplied evidence.
        for name in NAMES:
            with self.subTest(name=name):
                path, absent = self.root / name, self.root / (name + ".held")
                path.rename(absent)
                with self.assertRaises(FileNotFoundError):
                    check_saved.measured_protocol(self.env, self.root)
                absent.rename(path)

    def test_incomplete_or_extra_manifest_rejects(self):
        for name in NAMES:
            with self.subTest(name=name):
                hashes = dict(self.env["source_sha256"])
                hashes.pop(name)
                with self.assertRaises(AssertionError):
                    check_saved.measured_protocol({"source_sha256": hashes}, self.root)
        hashes = dict(self.env["source_sha256"], **{"extra.py": "0" * 64})
        with self.assertRaises(AssertionError):
            check_saved.measured_protocol({"source_sha256": hashes}, self.root)

    def test_non_directory_rejects(self):
        with self.assertRaises(AssertionError):
            check_saved.measured_protocol(self.env, self.root / "allocator.cpp")


if __name__ == "__main__":
    unittest.main()
