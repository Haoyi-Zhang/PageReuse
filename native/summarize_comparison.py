"""Recompute the three-way matched planner and complete-path comparison."""
import argparse
import json
import statistics
from pathlib import Path


from evidence import require, same, loads

def summarize(directory):
    directory = Path(directory)
    checks = json.loads((directory / 'checks.json').read_text(encoding='utf-8'))
    require(checks['cases'] == 207 and checks['identical_certificates'], 'scientific evidence gate')
    raw = [loads(s) for s in (directory / 'samples.jsonl').read_text(encoding='utf-8').splitlines()]
    require(len(raw) == len(checks['panel']) * checks['pairs'] * 3 == 378, 'scientific evidence gate')
    rows = {(r['id'], r['pair'], r['mode']): r for r in raw}
    require(len(rows) == len(raw), 'scientific evidence gate')
    report = []
    for case in checks['panel']:
        pairs = []
        for pair in range(checks['pairs']):
            a = {mode: rows[case, pair, mode] for mode in ('fresh', 'direct-union', 'incremental')}
            require(all(r['correct'] is True and all(type(r[k]) is int for k in ('frequency','planner_ticks','complete_ticks','planner_repeats','complete_repeats','pair')) and r['frequency'] > 0 and r['planner_ticks'] > 0 and r['complete_ticks'] > 0
                       and r['planner_repeats'] == 8 and r['complete_repeats'] == 4 for r in a.values()), 'scientific evidence gate')
            require(same(a['fresh']['actual_values'], a['direct-union']['actual_values']) and same(a['fresh']['actual_values'], a['incremental']['actual_values']), 'matched native value types')
            for key in ('actual_loads', 'publications'):
                require(a['direct-union'][key] == a['incremental'][key], 'scientific evidence gate')
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
