# Quantitative figure reproduction

This copy of the existing plotting script reads the same eight `tight.csv` rows.
It checks each cost, the case identities, and the complete weight sequence;
the curve is (2M+3)/(M+3), with a base-2 logarithmic weight axis and bound 2.
It is a modeled publication-cost ratio, not measured execution time.

From the artifact directory:

```sh
python -m pip install -r figures/requirements.txt
python -B figures/draw_tight.py
python -B figures/draw_complete_cost.py
```

The source rows match `results/tables/tight.csv`. Regenerating scientific tables
does not overwrite this script. The manuscript copy uses the same producer
and data, and keeps its 6.1-by-2.25-inch canvas and existing include scale.

The PDF embeds the Linux Libertine regular TrueType face (Type42); SVG keeps
vector glyph outlines. The unmodified font is licensed separately at
`../fonts/OFL-1.1.txt`. Supply `--font` or matching installed TeX/Matplotlib
regular TrueType if using the script without the bundled font. No substitute
is selected. Plotting is optional and changes no scientific-core dependency.

The complete-cost plot checks all 207 ranked values for each of three arms
against the independently recalculated retained summary. It retains the full
logarithmic ratio axis, parity line and empirical cumulative percentages.
No input, slow observation or tail point is removed. Its PDF/SVG outputs use
the same embedded Linux Libertine family. The PDF is vector-based; the 900-dpi
export setting also supports high-resolution raster exports without changing
the measurements. In a combined project, copy `complete-cost.pdf` and its SVG
to the sibling `paper/figures/` after reproduction.
