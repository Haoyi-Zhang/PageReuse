Generation-Aware Certificates for Page-List Reuse — electronic supplement

This supplement retains the declared-trace model, proofs, Python producer/checker, original generated inputs, historical campaigns and ledgers. It additionally contains a C++ CPU slot-buffer realization, C#/.NET direct-DP/checking harness, 207 native conformance records and all 308 predeclared paired timing samples with actual mandatory byte results. Complete observations and samples are losslessly compressed in results/native-campaign; no binary or compiler cache is included.

Start with README.md and docs/reproduction.md. The clean verification commands are:

  python -B .github/scripts/check_repository.py
  python -B tests/semantic_regressions.py --out semantic-results
  python tests/contracts.py --out contract-results
  python tests/final_replay.py --out final-replay-results
  python tools/campaign.py --out reproduced
  python tools/summarize.py --campaign reproduced --out reproduced-tables
  python -B tests/check_reproduction.py --campaign reproduced --tables reproduced-tables

The retained sources passed 32774 campaign obligations, 247 contract obligations, and 750 replay obligations in a historical clean Linux reproduction. Every reported non-timing campaign outcome matched the earlier retained pass. The original frozen ledger had already closed at 150000 / 150000; the later 33771-obligation validation is recorded separately, bringing that historical total to 183771 without satisfying the original cumulative ceiling. Subsequent Windows library and focused regression attempts added 32610 obligations, including the failed citation regression, and are described separately in docs/reproduction.md. The added CPU campaign is separate: all mandatory outputs match, but complete-path paired medians regress by 1.672--121.481 including direct-DP setup. Run python -B native/check_saved.py results/native-campaign to verify saved evidence without native execution. No public serving, GPU/attention-quality, concurrent-reclamation, proof-assistant, independent-team or submission claim follows.
