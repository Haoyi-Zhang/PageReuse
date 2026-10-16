"""Small record-coverage controls; no native execution or measurements."""
from copy import deepcopy
import unittest
from unittest.mock import patch
import check_native

class ObservationGroups(unittest.TestCase):
    def audit(self, rows):
        keys={('fixture','baseline'),('fixture','certified')}
        event={'kind':'publish','step':0,'value':0}
        with patch.object(check_native,'expected_events',return_value=iter([event])):
            # Each requested group needs its own generator.
            with patch.object(check_native,'expected_events',side_effect=lambda *args: iter([event])):
                return check_native.audit_observations(rows,{'fixture':{}},{'fixture':{}},keys)
    def rows(self):
        return [{'id':'fixture','mode':mode,'ev':{'kind':'publish','step':0,'value':0}}
                for mode in ('baseline','certified')]
    def test_complete_distinct_groups(self):
        self.assertEqual(self.audit(self.rows())['native_observation_groups'],2)
    def test_duplicate_group_does_not_replace_coverage(self):
        rows=self.rows()
        with self.assertRaisesRegex(AssertionError,'duplicate observation group'):
            self.audit(rows+[deepcopy(rows[0])])
    def test_missing_or_empty_groups(self):
        for rows in ([],self.rows()[:1]):
            with self.subTest(rows=rows),self.assertRaises(AssertionError): self.audit(rows)
    def test_unknown_mode_is_rejected(self):
        rows=self.rows();rows[0]['mode']='unknown'
        with self.assertRaisesRegex(AssertionError,'unexpected observation group'): self.audit(rows)

if __name__=='__main__': unittest.main(verbosity=2)
