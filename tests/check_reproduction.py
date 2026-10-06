"""Fail if a completed fresh campaign differs from retained scientific outputs.

Only saved-data comparisons are performed. Timers/RSS are deliberately not
gates and this is not a new optimization, checker or experiment invocation.
"""
import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--campaign', type=Path, required=True)
    ap.add_argument('--tables', type=Path, required=True)
    args = ap.parse_args()
    compared = {}
    for name, count in [('positive', 200), ('certificates', 200), ('mutations', 400),
                        ('sensitivity', 32), ('ablations', 16)]:
        old = jsonl(ROOT / 'results/campaign' / (name + '.jsonl'))
        new = jsonl(args.campaign / (name + '.jsonl'))
        assert len(old) == len(new) == count, (name, len(old), len(new))
        if name == 'positive':
            old = [{k: v for k, v in row.items() if k not in {'producer_ns', 'checker_ns'}} for row in old]
            new = [{k: v for k, v in row.items() if k not in {'producer_ns', 'checker_ns'}} for row in new]
        assert old == new, name
        compared[name] = count
    ignored = {'cpu_s', 'wall_s', 'peak_rss_kib'}
    old_summary = json.loads((ROOT / 'results/campaign/summary.json').read_text(encoding='utf-8'))
    new_summary = json.loads((args.campaign / 'summary.json').read_text(encoding='utf-8'))
    assert {k: v for k, v in old_summary.items() if k not in ignored} == {
        k: v for k, v in new_summary.items() if k not in ignored}
    assert new_summary['status'] == 'finite_campaign_passed'
    table_names = ['coverage', 'baselines', 'mutations', 'tight', 'sensitivity_pairs', 'sensitivity', 'ablations']
    for name in table_names:
        def read(base):
            with (base / (name + '.csv')).open(newline='', encoding='utf-8') as source:
                return [{k: v for k, v in row.items() if not k.startswith('median_')}
                        for row in csv.DictReader(source)]
        assert read(ROOT / 'results/tables') == read(args.tables), name
    assert json.loads((ROOT / 'results/tables/inventory.json').read_text(encoding='utf-8')) == json.loads(
        (args.tables / 'inventory.json').read_text(encoding='utf-8'))
    print(json.dumps({'compared_rows': compared, 'compared_tables': len(table_names),
                      'scope': 'Saved non-timing outputs only; no live sources, optimization or scientific obligations added.'}, sort_keys=True))


if __name__ == '__main__':
    main()
