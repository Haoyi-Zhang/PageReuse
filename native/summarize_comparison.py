"""Recompute the three-way matched planner and complete-path comparison."""
import argparse
import json
import statistics
from pathlib import Path


def summarize(directory):
    directory = Path(directory)
    checks = json.loads((directory / 'checks.json').read_text(encoding='utf-8'))
    assert checks['cases'] == 207 and checks['identical_certificates']
    raw = [json.loads(s) for s in (directory / 'samples.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(raw) == len(checks['panel']) * checks['pairs'] * 3 == 378
    rows = {(r['id'], r['pair'], r['mode']): r for r in raw}
    assert len(rows) == len(raw)
    report = []
    for case in checks['panel']:
        pairs = []
        for pair in range(checks['pairs']):
            a = {mode: rows[case, pair, mode] for mode in ('fresh', 'direct-union', 'incremental')}
            assert all(r['correct'] and r['frequency'] > 0 and r['planner_ticks'] > 0 and r['complete_ticks'] > 0
                       and r['planner_repeats'] == 8 and r['complete_repeats'] == 4 for r in a.values())
            assert a['fresh']['actual_values'] == a['direct-union']['actual_values'] == a['incremental']['actual_values']
            for key in ('actual_loads', 'publications'):
                assert a['direct-union'][key] == a['incremental'][key]
            pairs.append(a)
        def ratio(numerator, denominator, field):
            return statistics.median(p[numerator][field] / p[denominator][field] for p in pairs)
        report.append(dict(id=case,
                           planner_reference_over_incremental=ratio('direct-union', 'incremental', 'planner_ticks'),
                           full_reference_over_incremental=ratio('direct-union', 'incremental', 'complete_ticks'),
                           full_incremental_over_fresh=ratio('incremental', 'fresh', 'complete_ticks'),
                           incremental_faster_than_fresh_pairs=sum(p['incremental']['complete_ticks'] < p['fresh']['complete_ticks'] for p in pairs),
                           incremental_loads=pairs[0]['incremental']['actual_loads'],
                           fresh_loads=pairs[0]['fresh']['actual_loads'],
                           incremental_publications=pairs[0]['incremental']['publications'],
                           fresh_publications=pairs[0]['fresh']['publications']))
    summary = dict(raw_samples=len(raw), pairs_per_case=9, cases=report, exact_certificate_agreements=207,
                   complete_path='plan/check/allocate/materialize/native execute/project/free',
                   excluded_from_timer='compilation, JSON input decoding, output comparison, record serialization')
    (directory / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    print(json.dumps(summarize(args.directory)))
