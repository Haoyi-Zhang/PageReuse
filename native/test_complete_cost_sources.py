"""Inert source-binding controls; no native execution or timing campaign."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import check_complete_cost as target


class SourceBindings(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.sources={name:'# inert original source: '+name+'\n' for name in target.SOURCES}
        self.bindings={name:hashlib.sha256(text.encode()).hexdigest().upper() for name,text in self.sources.items()}
        for name,text in self.sources.items():
            p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(text.encode())
        self.context={name:self.sources[name] for name in ('native/evidence.py','native/check_complete_cost.py')}
        self.context_path=self.root/'data/measured_complete_cost_checkers.json'
        self.context_path.parent.mkdir()
        self.write_context()
        p=patch.object(target,'ROOT',self.root);p.start();self.addCleanup(p.stop)

    def write_context(self):
        self.context_path.write_text(json.dumps(self.context),encoding='utf-8')

    def changed_helper(self):
        (self.root/'native/evidence.py').write_bytes(b'# strengthened current record reader\n')

    def test_current_context_needs_no_fallback(self):
        self.context_path.unlink()
        self.assertEqual(target.source_binding_state(self.bindings)['retained_checker_sources'],[])

    def test_changed_helpers_have_exact_original_bindings(self):
        self.changed_helper()
        (self.root/'native/check_complete_cost.py').write_bytes(b'# current binding reader\n')
        result=target.source_binding_state(self.bindings)
        self.assertEqual(result['retained_checker_sources'],sorted(self.context))
        self.assertFalse(result['archived_sources_executed'])

    def test_changed_executor_is_rejected(self):
        self.changed_helper();(self.root/'native/allocator.cpp').write_bytes(b'changed executor')
        with self.assertRaises(AssertionError):target.source_binding_state(self.bindings)

    def test_changed_planner_is_rejected(self):
        (self.root/'src/producer.py').write_bytes(b'changed planner')
        with self.assertRaises(AssertionError):target.source_binding_state(self.bindings)

    def test_missing_context_is_rejected(self):
        self.changed_helper();self.context_path.unlink()
        with self.assertRaises(FileNotFoundError):target.source_binding_state(self.bindings)

    def test_mutated_historical_helper_is_rejected(self):
        self.changed_helper();self.context['native/evidence.py']+='altered';self.write_context()
        with self.assertRaises(AssertionError):target.source_binding_state(self.bindings)

    def test_partial_context_is_rejected(self):
        self.changed_helper();del self.context['native/check_complete_cost.py'];self.write_context()
        with self.assertRaises(AssertionError):target.source_binding_state(self.bindings)

    def test_unknown_context_is_rejected(self):
        self.changed_helper();self.context['native/allocator.cpp']='invented';self.write_context()
        with self.assertRaises(AssertionError):target.source_binding_state(self.bindings)

    def test_duplicate_context_key_is_rejected(self):
        self.changed_helper();self.context_path.write_text('{"x":"a","x":"b"}',encoding='utf-8')
        with self.assertRaises(AssertionError):target.source_binding_state(self.bindings)

    def test_unknown_binding_is_rejected(self):
        b={**self.bindings,'unrecorded':'0'*64}
        with self.assertRaises(AssertionError):target.source_binding_state(b)

    def test_retained_text_is_never_executed(self):
        self.changed_helper()
        name='native/evidence.py';self.context[name]="raise RuntimeError('must not execute')\n"
        self.bindings[name]=hashlib.sha256(self.context[name].encode()).hexdigest().upper();self.write_context()
        self.assertEqual(target.source_binding_state(self.bindings)['retained_checker_sources'],[name])


if __name__=='__main__':unittest.main(verbosity=2)
