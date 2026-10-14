"""Inert record admission controls, not new workload or performance samples."""
import tempfile, unittest
from pathlib import Path
import check_native
import check_workflow
from evidence import require, same, loads

class Evidence(unittest.TestCase):
    def test_type_sensitive_values(self):
        for a,b in ((False,0),(True,1),(0.0,0),([True],[1]),({'v':False},{'v':0})):
            self.assertFalse(same(a,b))
        self.assertTrue(same({'v':[0,1,True]},{'v':[0,1,True]}))

    def test_explicit_gate(self):
        with self.assertRaisesRegex(AssertionError,'owned-negative'):require(False,'owned-negative')

    def test_duplicate_and_nonfinite_json(self):
        for raw in ('{"v":1,"v":2}','{"v":NaN}','{"v":Infinity}','{"v":-Infinity}'):
            with self.subTest(raw=raw),self.assertRaises(AssertionError):loads(raw)

    def test_reader_uses_strict_json(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'inert.jsonl';p.write_text('{"v":1,"v":2}\n')
            with self.assertRaises(AssertionError):list(check_native.records(p))
            with self.assertRaises(AssertionError):check_workflow.rows(p)

    def test_no_missing_native_accounting_field(self):
        row=dict.fromkeys(check_workflow.EXECUTION_FIELDS,0)
        check_workflow.execution_shape(row)
        for name in check_workflow.EXECUTION_FIELDS:
            with self.subTest(name=name),self.assertRaises(AssertionError):
                check_workflow.execution_shape({k:v for k,v in row.items() if k!=name})

if __name__=='__main__':unittest.main()
