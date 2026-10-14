"""Portable retained-device-result and admission regressions; no driver calls."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import gpu_pages as study
from cuda_page_driver import PageDevice


class DeviceEvidence(unittest.TestCase):
    def test_complete_retained_device_outputs(self):
        counts = study.audit(study.ROOT/'results/gpu-pages')
        self.assertEqual((counts['inputs'],counts['replays'],counts['queries']),(207,414,4354))
        self.assertGreater(counts['zero_cap_consultations'],0)

    def test_payload_is_little_endian_bit_pattern(self):
        p = dict(content=2147483647,generation=2147483647,kv_group=31,format='fp16')
        self.assertEqual(study.payload(p,127),(131*p['content']+17*p['generation']+217+29*127)&65535)
        p['format']='int8'
        self.assertLessEqual(study.payload(p,127),255)

    def test_zero_cap_preserves_descriptor_consultation(self):
        item = next(r for r in study.inputs() if r['id']=='native-edge-capzero')
        cert = study.plan(item['trace'],'exact')
        found = False
        for t in range(len(item['trace']['steps'])):
            _,ds,values = study.shape(item['trace'],cert,t)
            B = item['trace']['page_size']
            found |= any(values[j*B:(j+1)*B] == [study.SENTINEL]*B for j in range(len(ds)))
        self.assertTrue(found)

    def test_admission_rejects_bad_types_and_extents_before_driver(self):
        device = object.__new__(PageDevice)
        valid = [[0,0,1,2,4,0]]
        for args in ((valid,True,3,8),(valid,4,True,8),(valid,4,3,True),
                     ([[0,0,True,2,4,0]],4,3,8),([[0,1,1,2,4,0]],4,3,8),
                     ([[0,0,1,2,5,0]],4,3,16)):
            with self.assertRaises(ValueError):
                device.query(*args)
        for index,length in ((True,0),(-1,0),(4,0),(0,-1),(0,65601),(0,True)):
            with self.assertRaises(ValueError):
                device.read(index,length)

    def test_generation_control_cannot_be_omitted(self):
        directory = study.ROOT/'results/gpu-pages'
        rows = study.bounded_rows(directory/'executions.jsonl.gz')
        source = next(r for r in rows if r['generation_controls'])
        for field in ('values','mandatory','generation_control'):
            bad = copy.deepcopy(source)
            step = next(s for s in bad['steps'] if s['generation_control'])
            step[field] = []
            with patch.object(study,'bounded_rows',side_effect=lambda p: [bad] if p.parent == directory else rows):
                # Use the real frozen-input loader; only execution rows change.
                with patch.object(study,'inputs',return_value=self.inputs):
                    with self.assertRaises(AssertionError):
                        study.audit(directory)

    @classmethod
    def setUpClass(cls):
        cls.inputs = study.inputs()

    def test_decompression_budget_checked_on_actual_read(self):
        import gzip
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'big.gz'
            with gzip.open(path,'wb') as f:
                f.write(b' '*33)
            with patch.object(study,'MAX_BYTES',32):
                with self.assertRaises(AssertionError):
                    study.bounded_rows(path)


if __name__ == '__main__':
    unittest.main()
