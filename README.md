# Page-selection safety certificates

A standalone artifact for generation-aware page-list reuse on complete finite sequential traces. The standard-library Python core retains the frozen synthetic inputs, source-separated producer/checker, written proofs, tiny oracles and historical results. A C++ CPU buffer adapter with a C#/.NET harness adds real slot allocation and masked byte loads, conformance records and a separately declared paired overhead campaign for *Generation-Aware Certificates for Page-List Reuse*.

This is **not** LServe, a GPU memory checker, a concurrent page-table protocol, an online selector or an attention-quality guarantee. The CPU bridge realizes the small sequential lane-array contract, not a production KV cache. The historical venue-significance assessment remains negative; the native addition supplies measured CPU evidence without establishing TACO readiness. See `docs/novelty-assessment.md` and `docs/literature-scope.md`.

## Native CPU evidence

The native adapter passes 207 positive cases, matches all 200 retained optima,
rejects the 400 retained checker controls, and passes explicit empty/null-list,
zero-cap, address/integer and resident-metadata checks. A source-separated audit
checks 741951 actual transition, lease, address and load events. The unchanged
Python checker accepts every new plan.

The predeclared 14-case campaign retains all 308 samples / 154 paired comparisons.
Mandatory-lane actual values match the fresh baseline. Complete-path paired
medians are slower under certification on every case, by factors 1.672--121.481,
including the transparent direct-DP harness setup. All seven overhead phases,
extra loads and negative gains are retained; these are not timings of the Python
range-tree producer or evidence of GPU, attention or production-serving gains.

From this directory, check the saved public records without compilation or
native execution:

```sh
python -B native/check_saved.py results/native-campaign
```

`results/native-campaign/` includes readable summaries, plans, counts and
path-redacted environment/source bindings. Complete observations and samples
are losslessly compressed as `.jsonl.gz`. Its README explains decompression for
the original working-file checkers. Native reproduction uses parameterized
`native/bounded.ps1`; see `native/README.md`. It requires existing Windows x64
PowerShell/Roslyn and Zig, installs nothing, and keeps correctness separate from
explicitly reserved performance runs. The Linux scientific commands below are
the unchanged Python workflow, not a native performance CI.

## Verify the delivered final sources

From this directory on Linux with Python 3.10 or newer:

```sh
python -B .github/scripts/check_repository.py
python -B tests/semantic_regressions.py --out semantic-results
python tests/contracts.py --out contract-results
python tests/final_replay.py --out final-replay-results
python tools/campaign.py --out reproduced
python tools/summarize.py --campaign reproduced --out reproduced-tables
python -B tests/check_reproduction.py --campaign reproduced --tables reproduced-tables
```

Use new or empty output directories. The contract suite exercises 34 named parser, CLI, producer, checker, and malformed-input cases plus every cut mask of eight existing tiny parents. The replay checks all 200 positives in safety mode, all 48 tiny certificates in strict mode, and two freshly regenerated certificates. The full campaign checks 200 positives, 48 exhaustive tiny cases, 400 constructed negative controls, 32 visit-price variants, fixed baselines on 56 identifiers, and two lifetime ablations on eight identifiers. The summarizer performs arithmetic only over saved JSONL results.

A clean reproduction of the delivered final sources passed all three scientific runners. It reproduced every non-timing campaign field: `certificates.jsonl`, `mutations.jsonl`, `sensitivity.jsonl`, and `ablations.jsonl` were byte-identical to the earlier retained pass, while all 200 positive rows differed only in run-specific producer/checker timers. The machine-readable comparison is `results/reproduction-comparison.json`.

## Accounting chronology

The original development ledger closed exactly at **150000 / 150000** counted obligations: 149003 before closeout, then 247 contract obligations and 750 final-source replay obligations. That historical ledger remains unchanged.

After the freeze, a separate clean validation executed the bounded-reader-repaired sources: 32774 campaign obligations, 247 contract obligations, and 750 replay obligations. This later validation is not backfilled into the historical ledger. The recorded development and historical Linux reproduction total is **183771** counted obligations, exceeding the original cumulative ceiling by 33771. The deviation is disclosed in `results/resource-accounting.json`; deleting outputs or relabeling the run would not repair it. Subsequent local checks are additional executions, recorded separately in `docs/reproduction.md`; 183771 is not an ever-current cumulative total. The historical reproduction was used only to test reproduction, not to select inputs, tune methods, or broaden claims.

The three historical Linux campaign/contract/replay runners use one pinned worker, a 2500 MiB address-space limit, a 90-second CPU limit, and explicit enumeration guards. The small `semantic_regressions.py` runner is portable and relies on its caller for process limits. No package installation, network, GPU, solver, model weights, API, private data, paper directory, or unseen cache is needed. Exact provenance is in `docs/reproduction.md`.

The `scientific-checks.yml` workflow is configured for the flat artifact repository on Ubuntu 24.04, including pushes to `main`. Its scientific sequence has a 180-second wall limit, 120-second shell CPU limit, 2500 MiB address-space limit, retained assertion/failure gates, and always-attempted raw-output upload. It also compares regenerated non-timing campaign rows and tables with the retained records. Preparing this workflow is not evidence that remote CI has run.

## Check one certificate

Extract an existing trace without regenerating data:

```sh
python -c 'import json; from pathlib import Path; r=json.loads(Path("inputs/traces.jsonl").read_text().splitlines()[2]); Path("trace.json").write_text(json.dumps(r["trace"]))'
python src/producer.py trace.json certificate.json
python src/checker.py trace.json certificate.json
```

The checker returns exit code 0 for acceptance and 2 for rejection. `--safety-only` omits minimum-cost certification. The checker imports no producer code, but both programs were developed in the same development process; this is source separation, not independent-team verification. Both CLI readers are bounded to the documented input size, and the producer remains untrusted by the checker.

## Evidence map

- `docs/model.md` — exact finite language and assumptions.
- `proofs/theorems.md` — written general arguments, not proof-assistant proofs.
- `inputs/` — frozen generated traces and retained controls.
- `results/campaign/` — final clean full campaign over the delivered sources.
- `native/` — C++ CPU execution, C# direct-DP/checking harness, fixed measurement protocol and saved-evidence checkers.
- `results/native-campaign/` — complete compressed native records and all paired overhead phases; synthetic CPU results only.
- `results/contracts/` — final clean contract and cut-formulation run.
- `results/final-replay/` — final-source replay over all positives, all tiny cases, and two fresh producer outputs.
- `results/reproduction-comparison.json` — semantic comparison with the pre-repair retained campaign.
- `results/resource-accounting.json` — historical ledger and post-freeze validation accounting.
- `claim_evidence_ledger.csv` — claim-by-claim maturity and limitations.
- `external_resources.csv` — scholarly/official source inventory and redistribution status.
- `docs/bibliography-audit.csv` / `.md` — 60 row-level canonical-record checks.
- `docs/calibration-matrix.md` / `.csv` — 13+5+7 full-paper calibration.
- `docs/literature-scope.md` — inclusion rules and synthesis.
- `docs/novelty-assessment.md` — adversarial novelty/significance decision.
- `docs/venue-rules.md` — current format/policy record and retrieval limits.
- `readme.txt` — short electronic-supplement description.

The abstract safety conclusions require truthful bindings, initialization, lives,
masks and sequential loads. The CPU adapter supplies a written refinement for
its own controlled buffer and directly checks resident state. It does not
authenticate an external allocator. Weighted descriptor publication remains a
different objective from the separately measured CPU runtime; fixed-format
numerical range bounds are not attention-approximation guarantees.

AI assistance was substantive in research design, proofs, code, synthetic data, execution, analysis, validation, writing and self-audit. No independent external review, machine-checked proof or production applicability is claimed. Original code and synthetic data use the included MIT license. No third-party paper PDF or serving-runtime implementation is redistributed.
