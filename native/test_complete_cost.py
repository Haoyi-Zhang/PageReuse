"""Admission regressions: normal and -O must reject malformed measurement data."""
import copy,unittest
from check_complete_cost import shape,ratio,PHASES
def sample():
    return dict(id='owned-control',arm='ordinary-exact',round=0,position=0,objective='rho0-publication',checker='optimality',frequency=10,full=dict(wall_ticks=7,process_cpu_100ns=0),phases={p:dict(wall_ticks=1,process_cpu_100ns=0) for p in PHASES},input_bytes=1,published_bytes=2,published_utf8='{}',actual_values=[],actual_loads=0,actual_bytes=0,publications=1,descriptor_copies=0,sink=0,arena_bytes=1,passed=True)
class Gates(unittest.TestCase):
    def test_valid_zero_cpu(self):shape(sample());self.assertIsNone(ratio(0,0));self.assertEqual(ratio(0,7),0)
    def test_boolean_not_integer(self):
        r=sample();r['full']['process_cpu_100ns']=False
        with self.assertRaises(AssertionError):shape(r)
    def test_incomplete_phases(self):
        r=sample();del r['phases']['publication']
        with self.assertRaises(AssertionError):shape(r)
    def test_fake_phase_total(self):
        r=sample();r['full']['wall_ticks']=6
        with self.assertRaises(AssertionError):shape(r)
    def test_wrong_guarantee(self):
        r=sample();r['checker']='safety-only'
        with self.assertRaises(AssertionError):shape(r)
    def test_negative_clock(self):
        r=sample();r['phases']['native']['wall_ticks']=-1
        with self.assertRaises(AssertionError):shape(r)
    def test_float_clock(self):
        r=sample();r['full']['wall_ticks']=7.0
        with self.assertRaises(AssertionError):shape(r)
    def test_missing_cpu_not_zero(self):
        r=sample();r['full']['process_cpu_100ns']=None
        with self.assertRaises(AssertionError):shape(r)
    def test_unknown_field(self):
        r=sample();r['omitted_work']=True
        with self.assertRaises(AssertionError):shape(r)
if __name__=='__main__':unittest.main(verbosity=2)
