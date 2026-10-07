Generation-Aware Certificates for Page-List Reuse — electronic supplement

This supplement contains the declared-trace model, proofs, Python producer/checker, generated inputs, retained campaigns and ledgers. It also contains a C++ CPU slot-buffer realization, C#/.NET incremental backward-DP/checking harness, 207 native conformance records and all 308 predeclared paired timing samples with actual mandatory byte results. Two three-arm planner comparisons retain a further 756 samples. Complete observations and phase samples are losslessly compressed in results/native-campaign; comparison samples are in results/native-comparison. No binary or compiler cache is included.

Start with README.md and docs/reproduction.md. The clean verification commands are:

  python -B .github/scripts/check_repository.py
  python -B tests/semantic_regressions.py --out semantic-results
  python tests/contracts.py --out contract-results
  python tests/final_replay.py --out final-replay-results
  python tools/campaign.py --out reproduced
  python tools/summarize.py --campaign reproduced --out reproduced-tables
  python -B tests/check_reproduction.py --campaign reproduced --tables reproduced-tables

The Python campaigns, contracts and replay tests are described in docs/reproduction.md. The native planner produces certificates identical to the direct-union comparator on all 207 cases. Planning and reference-relative full-path medians improve on every declared case in both complete comparison runs. In the separate phase campaign, the full-path median remains 1.037--1.245 times fresh publication. Run python -B native/check_saved.py results/native-campaign to check saved measurements against their source bindings and semantic outputs without native execution. These experiments concern a sequential synthetic CPU buffer, not public serving, GPU execution or attention quality.
