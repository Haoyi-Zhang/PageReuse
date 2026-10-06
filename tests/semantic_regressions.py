"""Small, owned-input regressions for the declared contract and QUEST mapping.

No external program, runtime, dataset or network is exercised. The source claim
was checked against the author paper, arXiv:2406.10774v1, Sections 4.3.1--4.3.2;
the PMLR landing-page abstract reverses the two speedup labels.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import csv
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tools')]
import checker
import producer
from generate import typed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists() and any(args.out.iterdir()):
        parser.error('output must be new or empty')
    args.out.mkdir(parents=True, exist_ok=True)
    cpu, wall = time.process_time(), time.monotonic()
    counters = {'certificate_replays': 0, 'checker_intervals': 0,
                'producer_minimum_queries': 0}
    tests = 0
    with (args.out / 'cases.jsonl').open('w', encoding='utf-8') as output:
        def verify(name, trace, cert, accepted=True, code=None, optimal=True):
            nonlocal tests
            answer = checker.check(trace, cert, optimal=optimal)
            counters['certificate_replays'] += answer['certificate_obligations']
            counters['checker_intervals'] += answer['span_obligations']
            output.write(json.dumps({'name': name, 'trace': trace, 'certificate': cert,
                                     'result': answer}, sort_keys=True) + '\n')
            output.flush()
            assert answer['accepted'] == accepted, (name, answer)
            if code is not None:
                assert answer['code'] == code, (name, answer)
            tests += 1
            return answer

        def solve(trace):
            counters['producer_minimum_queries'] += len(trace['steps'])
            return producer.solve(trace)['certificate']

        empty = typed([set(), set(), set()], [(0, 2)], [1], setup=0)
        cert = solve(empty)
        assert cert['total_cost'] == 0 and cert['potentials'] == [0] * 4
        verify('empty-unions-zero-cost', empty, cert)
        tied = producer.make_certificate(empty, [[0, 0], [1, 1], [2, 2]], [0] * 4)
        verify('different-tied-optimal-partition', empty, tied)
        charged = deepcopy(empty)
        charged['setup'] = 7
        cert = solve(charged)
        assert cert['total_cost'] == 7 and len(cert['epochs']) == 1
        verify('empty-unions-positive-setup', charged, cert)

        late = typed([set(), {0}, set()], [(1, 2)], [3])
        cert = solve(late)
        assert cert['epochs'][0]['end'] == 0
        verify('birth-after-empty-prefix', late, cert)
        early = typed([{0}, set(), set()], [(0, 0)], [3])
        cert = solve(early)
        assert cert['epochs'][0]['end'] == 0
        verify('expiry-before-empty-suffix', early, cert)

        # A zero causal cap does not waive the declared descriptor-life premise.
        stale = producer.make_certificate(early, [[0, 2]], cert['potentials'])
        early['pages'][0]['base'] = 3
        early['steps'][0]['frontier'] = 3
        stale['frontiers'][0] = 3
        verify('masked-stale-descriptor', early, stale, False, 'lifetime', optimal=False)

        aliases = typed([{0}, {0}, {0}], [(0, 2)], [5], alias=True, cycle=True)
        aliases['steps'][1]['nodes'][0]['atoms'] *= 2
        cert = solve(aliases)
        assert cert['total_cost'] == 6
        verify('cyclic-alias-duplicate-atoms-one-charge', aliases, cert)

        # A live, fully masked extra page is safe but is not a canonical optimum.
        extras = typed([{0}], [(0, 0), (0, 0)], [2, 3])
        extras['pages'][1]['base'] = 3
        cert = solve(extras)
        extra = deepcopy(cert)
        p = extras['pages'][1]
        extra['epochs'][0]['pages'].append([1, p['slot'], p['generation'], p['content'], p['format'], p['kv_group']])
        extra['epochs'][0]['cost'] += 3
        extra['total_cost'] += 3
        verify('masked-live-extra-safety', extras, extra, optimal=False)
        verify('masked-live-extra-not-optimal', extras, extra, False, 'nonminimal_epoch')

        boundcase = typed([{0}, {0}, {0}], [(0, 2)], [2**20], setup=2**20)
        cert = solve(boundcase)
        verify('largest-admitted-page-and-setup-weight', boundcase, cert)
        bound = 64 * (2**20 + (1 + 2**20 * 64) * 256 * 2**20)
        assert bound < 2**61
        tests += 1

        with (ROOT / 'docs/calibration-matrix.csv').open(newline='', encoding='utf-8') as source:
            rows = [row for row in csv.DictReader(source) if row['work'] == 'QUEST']
        assert len(rows) == 1
        mapping = rows[0]['proof_or_performance_argument']
        assert '7.03x self-attention' in mapping and '2.23x end-to-end' in mapping, mapping
        assert mapping in (ROOT / 'docs/calibration-matrix.md').read_text(encoding='utf-8')
        tests += 1

    summary = {'named_tests': tests, **counters,
               'counted_obligations': sum(counters.values()),
               'cpu_s': time.process_time() - cpu, 'wall_s': time.monotonic() - wall,
               'scope': 'Owned finite boundary cases and one frozen citation-to-metric mapping; not a full citation audit.'}
    (args.out / 'summary.json').write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps(summary, sort_keys=True))


if __name__ == '__main__':
    main()
