# Page-selection safety certificates

A standalone standard-library Python artifact for generation-aware page-list reuse on complete declared finite sequential traces. It contains the frozen synthetic inputs, a source-separated producer and checker, written proofs, exact tiny-instance oracles, the final clean campaign results, mutation controls, evidence ledgers, and completed literature/novelty calibration for *Generation-Aware Certificates for Page-List Reuse*.

This is **not** an implementation of LServe, a native GPU memory checker, a concurrent page-table protocol, an online selector, or an attention-quality guarantee. The audit concludes that the bounded result is a reproducible formal boundary study, not a submission-ready TACO systems contribution. See `docs/novelty-assessment.md` and `docs/literature-scope.md`.

## Verify the delivered final sources

From this directory on Linux with Python 3.10 or newer:

```sh
python -m compileall -q src tests tools
python tests/contracts.py --out contract-results
python tests/final_replay.py --out final-replay-results
python tools/campaign.py --out reproduced
python tools/summarize.py --campaign reproduced --out reproduced-tables
```

Use new or empty output directories. The contract suite exercises 34 named parser, CLI, producer, checker, and malformed-input cases plus every cut mask of eight existing tiny parents. The replay checks all 200 positives in safety mode, all 48 tiny certificates in strict mode, and two freshly regenerated certificates. The full campaign checks 200 positives, 48 exhaustive tiny cases, 400 constructed negative controls, 32 visit-price variants, fixed baselines on 56 identifiers, and two lifetime ablations on eight identifiers. The summarizer performs arithmetic only over saved JSONL results.

A clean reproduction of the delivered final sources passed all three scientific runners. It reproduced every non-timing campaign field: `certificates.jsonl`, `mutations.jsonl`, `sensitivity.jsonl`, and `ablations.jsonl` were byte-identical to the earlier retained pass, while all 200 positive rows differed only in run-specific producer/checker timers. The machine-readable comparison is `results/reproduction-comparison.json`.

## Accounting chronology

The original development ledger closed exactly at **150000 / 150000** counted obligations: 149003 before closeout, then 247 contract obligations and 750 final-source replay obligations. That historical ledger remains unchanged.

After the freeze, a separate clean validation executed the final bounded-reader-repaired sources: 32774 campaign obligations, 247 contract obligations, and 750 replay obligations. This later validation is not backfilled into the historical ledger. Across the complete execution history, the total is therefore **183771** counted obligations, exceeding the original cumulative ceiling by 33771. The deviation is disclosed in `results/resource-accounting.json`; deleting outputs or relabeling the run would not repair it. The additional run was used only to test reproduction, not to select inputs, tune methods, or broaden claims.

All scientific runners use one pinned worker, a 2500 MiB address-space limit, a 90-second CPU limit, and explicit enumeration guards. No package installation, network, GPU, solver, model weights, API, private data, paper directory, or unseen cache is needed. Exact provenance is in `docs/reproduction.md`.

## Check one certificate

Extract an existing trace without regenerating data:

```sh
python -c 'import json; from pathlib import Path; r=json.loads(Path("inputs/traces.jsonl").read_text().splitlines()[2]); Path("trace.json").write_text(json.dumps(r["trace"]))'
python src/producer.py trace.json certificate.json
python src/checker.py trace.json certificate.json
```

The checker returns exit code 0 for acceptance and 2 for rejection. `--safety-only` omits minimum-cost certification. The checker imports no producer code, but both programs were developed in the same AI-assisted process; this is source separation, not independent-team verification. Both CLI readers are bounded to the documented input size, and the producer remains untrusted by the checker.

## Evidence map

- `docs/model.md` — exact finite language and assumptions.
- `proofs/theorems.md` — written general arguments, not proof-assistant proofs.
- `inputs/` — frozen generated traces and retained controls.
- `results/campaign/` — final clean full campaign over the delivered sources.
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

All safety conclusions are relative to truthful declared bindings, initialization, lives, masks, and sequential abstract loads. The objective is weighted descriptor publication, not bytes transferred, latency, throughput, bandwidth, energy, or model accuracy. Fixed-format numerical range bounds are not attention-approximation guarantees.

AI involvement was substantive in hypotheses, proofs, code, synthetic inputs, local execution, analysis, validation, writing, and self-audit. No independent external review, human authorship agreement, machine-checked proof, submission, or production applicability is claimed. Original code and synthetic data use the included MIT license. No third-party paper PDF or serving-runtime implementation is redistributed.
