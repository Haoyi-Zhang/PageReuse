"""Draw all source-bound complete-cost CDF points as a vector figure."""
import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
from matplotlib import font_manager, pyplot as plt
from plot_font import PDF_METADATA, regular_libertine

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=HERE / 'complete-cost.pdf')
    args = parser.parse_args()
    with (ROOT / 'results/complete-cost/case-ratios.csv').open(newline='', encoding='utf-8') as stream:
        rows = list(csv.DictReader(stream))
    summary = json.loads((ROOT / 'results/complete-cost/summary.json').read_text())
    if summary['status'] != 'COMPLETE_COST_RECORDS_PASSED' or len(rows) != 207 or len(summary['cases']) != 207:
        raise ValueError('Complete admitted 207-input distribution required')
    columns = [('incremental', 'certified-incremental', 'Certified incremental', '#245a8d', '-'),
               ('range_min', 'certified-range-min', 'Certified range-min', '#a34b16', '--'),
               ('direct_union', 'certified-direct-union', 'Certified direct-union', '#454545', ':')]
    curves = {}
    for name, arm, _, _, _ in columns:
        observed = [float(row[name]) for row in rows]
        exact = sorted(value[arm]['median_paired_full_wall_ratio'] for value in summary['cases'].values())
        if observed != exact or any(v <= 0 for v in observed):
            raise ValueError('Plot distribution differs from complete admitted summary')
        curves[name] = observed
    if min(v for curve in curves.values() for v in curve) < .5 or max(v for curve in curves.values() for v in curve) > 110:
        raise ValueError('Declared axis bounds must contain every observation')
    percent = [float(row['percent']) for row in rows]
    if any(int(row['rank']) != i + 1 or percent[i] != 100 * (i + 1) / 207 for i, row in enumerate(rows)):
        raise ValueError('Ranks/percentages must retain every input')
    font = regular_libertine(HERE, ROOT / 'fonts/LinLibertine_Rah.ttf')
    family = font_manager.FontProperties(fname=str(font)).get_name()
    with plt.rc_context({'font.family': family, 'font.size': 9, 'pdf.fonttype': 42,
                         'svg.fonttype': 'path', 'savefig.dpi': 900, 'axes.linewidth': .65}):
        fig, ax = plt.subplots(figsize=(6.1, 2.05))
        fig.subplots_adjust(left=.105, right=.985, bottom=.26, top=.965)
        for name, _, label, color, style in columns:
            ax.plot(curves[name], percent, label=label, color=color, linestyle=style, linewidth=1.05)
        ax.set_xscale('log')
        ax.set(xlim=(.5, 110), ylim=(0, 100), xlabel='Full-wall ratio to ordinary exact',
               ylabel='Inputs at or below (%)')
        ticks = [.5, 1, 2, 5, 10, 20, 50, 100]
        ax.set_xticks(ticks, [str(v).removesuffix('.0') for v in ticks])
        ax.set_yticks([0, 25, 50, 75, 100])
        ax.axvline(1, color='.35', linestyle=(0, (4, 3)), linewidth=.75)
        ax.grid(which='major', color='.87', linewidth=.45)
        ax.set_axisbelow(True)
        ax.tick_params(which='major', length=3, width=.6)
        ax.tick_params(which='minor', bottom=False)
        ax.legend(loc='lower right', fontsize=8, framealpha=1, facecolor='white', edgecolor='.8')
        args.out.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(args.out, metadata=PDF_METADATA)
        fig.savefig(args.out.with_suffix('.svg'), metadata={'Creator': None, 'Date': None})
        plt.close(fig)
    print(f'Plotted all 207 points per arm with embedded {family}; no observations removed.')


if __name__ == '__main__':
    main()
