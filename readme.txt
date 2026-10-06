Generation-Aware Certificates for Page-List Reuse — electronic supplement

This standalone supplement contains the declared-trace model, written proofs, a source-separated producer and checker, exact generated inputs, a final clean finite campaign, contract tests, final-source replay, saved-data table generation, literature/novelty calibration, claim and resource ledgers, and reproduction documentation.

Start with README.md and docs/reproduction.md. The clean verification commands are:

  python -B .github/scripts/check_repository.py
  python -B tests/semantic_regressions.py --out semantic-results
  python tests/contracts.py --out contract-results
  python tests/final_replay.py --out final-replay-results
  python tools/campaign.py --out reproduced
  python tools/summarize.py --campaign reproduced --out reproduced-tables
  python -B tests/check_reproduction.py --campaign reproduced --tables reproduced-tables

The retained sources passed 32774 campaign obligations, 247 contract obligations, and 750 replay obligations in a historical clean Linux reproduction. Every reported non-timing campaign outcome matched the earlier retained pass. The original frozen ledger had already closed at 150000 / 150000; the later 33771-obligation validation is recorded separately, bringing that historical total to 183771 without satisfying the original cumulative ceiling. Subsequent Windows library and focused regression attempts added 32610 obligations, including the failed citation regression, and are described separately in docs/reproduction.md. No native runtime, public serving workload, GPU performance, model-quality guarantee, proof-assistant verification, independent external review, or submission is claimed.
