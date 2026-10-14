"""Owned tiny-oracle limits, active in normal and optimized Python."""
import sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'tools')]
import oracle
from generate import typed

class OracleAdmission(unittest.TestCase):
    def test_too_many_steps(self):
        tr=typed([{0}]*6,[(0,5)],[1])
        with self.assertRaisesRegex(AssertionError,'tiny oracle bounds'):oracle.analyze(tr)

    def test_too_many_pages(self):
        tr=typed([{0}],[(0,0)]*5,[1]*5)
        with self.assertRaisesRegex(AssertionError,'tiny oracle bounds'):oracle.analyze(tr)

    def test_single_step_exact_minimum(self):
        self.assertEqual(oracle.analyze(typed([{0}],[(0,0)],[3],setup=2)),
                         {'cost':5,'obligations':3,'intervals':1})

if __name__=='__main__':unittest.main()
