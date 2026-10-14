# Novelty and architecture-significance assessment

## Candidate claim examined

The candidate was that sparse-attention page selections could carry compact, independently replayable evidence proving both declared dependency coverage and minimum weighted descriptor-publication cost across reusable page-list epochs.

The input object is a complete sequential trace with:

- mandatory conjunctive logical dependencies;
- fixed logical-to-physical bindings at each step;
- immutable physical page incarnations with declared birth and expiry;
- constant selected-page lists within each epoch;
- truthful initialization and causal-frontier declarations; and
- an offline weighted publication objective over epoch boundaries.

## Decomposition against prior art

### Spatial least set

For mandatory conjunctive requirements, the least valid selected set is the image of all required logical objects under the fixed binding. Graph topology, cycles, interval structure, and laminar structure do not create a set-cover choice. This is an elementary canonicalization lemma and corrects the original hardness intuition; it is not a novel optimization paradigm.

### Temporal feasibility

Page births and expiries make a constant list invalid outside the intersection of the included incarnations’ live intervals. The project’s last-occurrence lifetime frontier gives an exact feasible-start characterization for the declared sequential language. This is useful and nontrivial within the model, but it assumes authoritative, truthful, immutable declarations and no concurrency.

### Optimization and certificate

The exact scheduler is a prefix shortest-path dynamic program. Its optimized implementation uses standard range-add/range-minimum machinery. The checker reconstructs interval semantics and verifies a shortest-path potential/lower-bound witness. Certifying-algorithm and translation-validation literature establishes the producer/checker pattern; shortest-path dual evidence is also standard. The contribution is the specialization and composition, not invention of those tools.

### Approximation result

At zero visit price, longest feasible reuse has a tight factor-two descriptor-publication bound. The retained analytic family reaches 2051 versus 1027 at weight 1024 and approaches two for larger weights. A birth-constrained control makes both policies cost 2052, preventing an invalid reuse argument. The theorem is specific to the declared offline objective; it is not a throughput, bandwidth, or online competitive guarantee.

## Strongest falsifiers considered

- **Arbitrary dependency graphs might make the spatial problem hard.** Refuted: mandatory fixed bindings leave no choice; the least image is immediate.
- **A single whole-trace list should always be cheapest.** Refuted by incarnation birth/expiry feasibility; the whole trace can be invalid.
- **Longest feasible reuse should be optimal.** Refuted by the retained weighted counterexample; the policy is only a tight two-approximation at zero visit price.
- **The same address implies the same page.** Refuted by generation/incarnation changes; address equality does not establish lifetime identity.
- **A safe certificate establishes optimality.** Refuted by safe-but-suboptimal controls, which pass safety-only mode and fail strict optimality mode.
- **Metadata coverage preserves attention quality.** Refuted by value-indistinguishable metadata instances; quality requires a separate numerical argument.
- **Source separation makes the checker independently verified.** Refuted: both programs were produced in the same development process, and neither code nor proof is mechanized.

None of these falsifiers invalidates the final bounded theorems; several invalidate broader interpretations that were therefore removed.

## Architecture and systems significance

The 13+5+7 full-paper calibration shows a consistent bar. TACO architecture/code-optimization articles and the closest serving systems connect their abstraction to at least one of:

- a native compiler/runtime/hardware mechanism;
- a refinement from program behavior to the abstraction;
- established or public workloads;
- measured overhead, performance, memory behavior, or quality; and
- sensitivity or comparison against realistic baselines.

The original packet supplied none of those deployment connections. The added
CPU bridge now realizes its own declared sequential buffer and measures actual
allocation, preparation, checking and masked loads. All 308 historical pre-index
samples are retained, and every case's complete-path median is slower under
certification by factors 1.037--1.245. Incremental backward unions substantially
reduce planning cost relative to direct union reconstruction, with identical
certificates and two complete matched repetitions retained. This supplies an
additional concrete algorithm-engineering result, not a serving speedup.
This connects synthetic traces to native CPU loads and measured overhead.
A separate CUDA consumer additionally replays fresh/exact plans on all 207
frozen inputs: 414 executions, 4,354 queries, 811,896 actual lane loads and
392,620 mandatory values match the byte oracle. Full device outputs and 4,154
resident-generation controls are retained in `results/gpu-pages/`. This is
functional device correspondence, with no GPU timing study. Representative
serving workloads, numerical attention and external allocator authentication
remain separate research obligations.

## Historical significance assessment

The historical assessment found a coherent composition-specific formal report
but insufficient originality and practical connection for the intended TACO
Original Research Article claim. Later CPU-buffer correspondence and overhead
evidence narrow the implementation gap; they do not independently establish
venue-level novelty or practical significance. The manuscript states its actual
sequential contract and measured negative results rather than claiming acceptance.

The historical closeout remains recorded separately:

- the bounded mathematical claims remain proved in writing and finitely checked;
- the literature gate is complete;
- the venue-significance gate is negative;
- a later clean final-source rerun is preserved with its disclosed 33771-obligation process overrun, unchanged by the new native evidence; and
- the subsequent authorized synthetic CPU campaign is recorded separately in `results/native-campaign/`, not backfilled into that ledger.

The limited CPU refinement and overhead evidence do not overturn the historical
venue-significance decision. The sequential device consumer narrows the byte
execution gap; concurrent reclamation, numerical attention and representative
serving evaluation remain distinct research obligations.
