# Reproduction and retained evidence

## Final clean execution

The delivered sources were executed from an isolated standalone-repository copy after the CLI readers had been repaired to read at most 4 MiB plus one sentinel byte. The run used only the files in this repository, one pinned worker, a 2500 MiB address-space limit, and a 90-second CPU limit. It required neither the manuscript, network, third-party packages, GPU, solver, model weights, API, nor omitted caches.

The full campaign in `results/campaign/` records:

- 200 accepted positive certificates;
- 48 exhaustive tiny selection/partition oracles;
- 400 targeted invalid or corrupted controls;
- 32 nonzero visit-price variants;
- fixed baselines on 56 parents;
- 16 lifetime-ablation certificates over eight parents; and
- 32774 counted obligations.

The final contract suite in `results/contracts/` exercised 34 named parser, schema, producer, checker, and command-line cases, all 48 cut masks of eight tiny parents, and 112 direct interval calculations. It passed 247 obligations. The final replay in `results/final-replay/` accepted all 200 positives in safety mode, all 48 tiny certificates in strict mode, and two freshly regenerated producer outputs. It passed 750 obligations.

The final campaign was compared with the earlier retained pass that preceded the bounded-reader edit. `certificates.jsonl`, `mutations.jsonl`, `sensitivity.jsonl`, and `ablations.jsonl` are byte-identical. All 200 positive rows agree after removing `producer_ns` and `checker_ns`; only those run-specific timers changed. The summary agrees after removing CPU, wall-time, and RSS diagnostics. `results/reproduction-comparison.json` records this comparison.

## Commands

Use new or empty output directories:

```sh
python -m compileall -q src tests tools
python tests/contracts.py --out contract-results
python tests/final_replay.py --out final-replay-results
python tools/campaign.py --out reproduced
python tools/summarize.py --campaign reproduced --out reproduced-tables
```

The arithmetic summarizer invokes no producer, checker, oracle, or optimizer. Its eight files should agree with `results/tables/`, apart from expected diagnostic timing changes when summarizing a newly timed campaign. The scientific counts and all non-timing tables are deterministic. `coverage.csv` deliberately reports the timers from the delivered final clean campaign rather than the earlier run.

## Accounting chronology and deviation

The original research ledger was frozen at 149003 obligations before closeout. Its 247-obligation contract run and 750-obligation replay closed that ledger exactly at **150000 / 150000**. The detailed historical accounting remains under `historical_frozen_campaign_ledger` in `results/resource-accounting.json`.

The later clean reproduction of the final sources added 32774 campaign, 247 contract, and 750 replay obligations. These 33771 obligations are recorded under `post_freeze_clean_reproduction`; they are not backfilled into the historical ledger. The complete execution history is therefore **183771** counted obligations. It exceeds the original cumulative ceiling by 33771, an irreversible process-contract deviation that is reported rather than hidden. The later run was confirmatory: it did not alter case inclusion, tune the implementation, select favorable outcomes, or expand the paper's claims.

A counted obligation is a candidate interval, exact selection or partition choice, certificate replay, or explicitly charged eligibility evaluation. It is not a CPU instruction, graph edge, or real memory access. The historical ledger includes a conservative 9000-operation allowance and an unretained failed pass, so it is an accounting record rather than instruction profiling.

CPU, wall, and RSS fields describe individual Python executions. They support no stable performance comparison. In contract summaries, child CPU is cumulative `RUSAGE_CHILDREN`; summed RSS maxima are conservative observations, not simultaneous peaks.

## Data-to-paper mapping

The saved-data summarizer reads every retained row. `coverage.csv` supports the size table, `mutations.csv` the rejection table, `baselines.csv` the 56-parent comparison, `sensitivity.csv` the weighted/unweighted visit table, and `tight.csv` the exact ratio plot. `sensitivity_pairs.csv` preserves the eight paired parents at all five prices. `ablations.csv` records both fixed eight-parent tests. The manuscript copy of `tight.csv` is checked against the repository file during packaging.

The 632 main campaign inputs comprise 200 positive parents, 400 constructed mutants, and 32 visit-price variants. Ablation and contract variants are diagnostics, not public workloads. Public-runtime-trace count is zero. The normalized and typed pilots are separate controls and are not added to the 200 positive-case corpus.

Mathematical arguments require reading the definitions and proofs; reproducing a command does not independently prove them. The tiny oracle assumes a well-formed input and enumerates all page subsets and cut masks only within its tiny bounds. The strict parser, declared abstract semantics, and correctness of the checker implementation remain trusted components. No native-kernel experiment, public serving workload, model-quality result, or independent-team assessment is present.
