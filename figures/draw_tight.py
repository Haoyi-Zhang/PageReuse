"""Draw the exact cost family with embedded Linux Libertine TrueType glyphs."""
import argparse
import csv
from fractions import Fraction
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
from matplotlib import font_manager, pyplot as plt
from plot_font import PDF_METADATA, regular_libertine

HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--font', type=Path, help='Linux Libertine regular TrueType font')
parser.add_argument('--data', type=Path, default=HERE / 'tight.csv')
parser.add_argument('--out', type=Path, default=HERE / 'tight.pdf')
args = parser.parse_args()
font = regular_libertine(HERE, args.font)
family = font_manager.FontProperties(fname=str(font)).get_name()
with args.data.open(encoding='utf-8', newline='') as stream:
    rows = list(csv.DictReader(stream))
if [int(row['weight']) for row in rows] != [1, 2, 4, 16, 64, 256, 1024, 65536]:
    raise ValueError('The complete declared eight-case family is required.')
for number, row in enumerate(rows, 48):
    if row['id'] != f'case-{number:03d}':
        raise ValueError('Unexpected case identity.')
    weight = int(row['weight'])
    ratio = Fraction(int(row['greedy']), int(row['optimal']))
    if int(row['optimal']) != weight + 3 or int(row['greedy']) != 2 * weight + 3:
        raise ValueError('Costs disagree with the declared family.')
    if abs(float(ratio) - float(row['ratio'])) > 1e-12:
        raise ValueError('Stored ratio disagrees with exact costs.')
with plt.rc_context({'font.family': family, 'font.size': 9, 'svg.fonttype': 'path', 'pdf.fonttype': 42,
                     'axes.linewidth': 0.65, 'savefig.dpi': 600}):
    figure, axis = plt.subplots(figsize=(6.1, 2.25))
    figure.subplots_adjust(left=0.13, right=0.95, bottom=0.25, top=0.93)
    axis.set_xscale('log', base=2)
    axis.plot([int(r['weight']) for r in rows], [float(r['ratio']) for r in rows],
              color='black', linewidth=1.1, marker='o', markersize=3.2)
    axis.axhline(2, color='0.35', linewidth=0.9, linestyle=(0, (4, 3)))
    axis.set(xlim=(1, 65536), ylim=(1.15, 2.07),
             xlabel='Heavy-page weight M', ylabel='Greedy cost / optimum')
    ticks = [1, 4, 16, 64, 256, 1024, 65536]
    axis.set_xticks(ticks, [str(v) for v in ticks])
    axis.set_yticks([1.25, 1.5, 1.75, 2.0])
    axis.grid(which='major', color='0.87', linewidth=0.5)
    axis.set_axisbelow(True)
    axis.tick_params(length=3, width=0.6)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    svg = args.out.with_suffix('.svg')
    figure.savefig(svg, metadata={'Creator': None, 'Date': None})
    figure.savefig(args.out, metadata=PDF_METADATA)
    plt.close(figure)
print(f'Plotted all {len(rows)} exact cases with embedded {family} TrueType.')
