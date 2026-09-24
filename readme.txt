Generation-Aware Certificates for Page-List Reuse — electronic supplement

This standalone supplement contains the declared-trace model, written proofs, a source-separated producer and checker, exact generated inputs, a final clean finite campaign, contract tests, final-source replay, saved-data table generation, literature/novelty calibration, claim and resource ledgers, and reproduction documentation.

Start with README.md and docs/reproduction.md. The clean verification commands are:

  python -m compileall -q src tests tools
  python tests/contracts.py --out contract-results
  python tests/final_replay.py --out final-replay-results
  python tools/campaign.py --out reproduced
  python tools/summarize.py --campaign reproduced --out reproduced-tables

The delivered final sources passed 32774 campaign obligations, 247 contract obligations, and 750 replay obligations in a separate clean reproduction. Every reported non-timing campaign outcome matched the earlier retained pass. The original frozen ledger had already closed at 150000 / 150000; the later 33771-obligation validation is recorded separately, so the complete execution history is 183771 and does not satisfy the original cumulative ceiling. No native runtime, public serving workload, GPU performance, model-quality guarantee, proof-assistant verification, independent review, or submission is claimed.
