# Literature scope and completed calibration

## Status and method

The project closeout includes a **13 same-venue + 5 influential/foundational + 7 adjacent-venue full-paper calibration**. This exceeds the required 12+5+5 threshold. The row-level evidence is in `calibration-matrix.md` and `calibration-matrix.csv`; the manuscript bibliography contains 60 relevant scholarly sources, all cited in the paper.

A work was counted as a full-paper calibration read only when the substantive paper was inspected far enough to record its motivating problem, general principle, correctness or performance argument, practical connection, evaluation breadth, artifact strength, narrative sequence, section pattern, and the role of figures or tables. An abstract, project page, metadata record, search snippet, or bibliography entry alone was not counted. Bibliography sizes were recorded only when directly available; no count was invented. “Full paper inspected” does not mean independently replicated.

The screening emphasized three questions:

1. Does prior work already state the same certificate object or theorem?
2. Which ingredients are established independently of this project?
3. What evidence does TACO or the adjacent serving literature require before an abstraction becomes a systems contribution?

The access date for the completed closeout is 2026-09-15. No third-party paper PDF is redistributed. Primary scholarly URLs and the exact role of each source are recorded in `external_resources.csv`.

## Completed calibration groups

### Same-venue TACO papers (13)

HeapCheck; GPUArmor; MetaSys; Compiler Support for Sparse Tensor Computations in MLIR; Freeway to Memory Level Parallelism in Slice-Out-of-Order Cores; The Forward Slice Core; Iterating Pointers; SMAUG; Reducing Minor Page Fault Overheads through Enhanced Page Walker; Fine-Grain Quantitative Analysis of Demand Paging in Unified Virtual Memory; Intermediate Address Space; DELTA; and PICO.

These papers are substantively different, but the recurring TACO pattern is stable: an architecture, compiler, runtime, or analysis mechanism is connected to executable behavior and evaluated on established applications, kernels, simulators, or hardware prototypes. Formal or analytical arguments strengthen those mechanisms; they do not replace the implementation-to-workload connection when a systems claim is made.

### Influential or foundational papers (5)

PagedAttention/vLLM; FlashAttention; Proof-Carrying Code; Alive2; and CompCert.

This group calibrates both sides of the project. PagedAttention and FlashAttention show the implementation and workload evidence behind influential serving and attention mechanisms. Proof-Carrying Code, Alive2, and CompCert show that a certificate is meaningful only relative to a precisely defined semantic connection and trusted base. The present checker validates a declared graph; it does not establish a refinement from native server behavior to that graph.

### Adjacent full papers (7)

LServe; QUEST; MInference; SnapKV; vAttention; UNIQUE; and SPIN.

The closest adjacent systems couple selection, compression, paging, or sparse execution to CUDA kernels, serving frameworks, real model evaluations, or end-to-end performance/quality measurements. They do not present this project’s exact serial certificate composition, but that absence is not a priority or significance claim.

## Technical synthesis

The following pieces are established or elementary rather than new general methods:

- With mandatory conjunctive requirements and fixed bindings, the least selected page set is the image/union of those requirements, even for cyclic dependency graphs.
- Prefix dynamic programming, shortest-path potentials, range-minimum/range-add structures, and producer/checker separation are standard tools.
- Spatial and temporal memory-safety enforcement has a much broader runtime and hardware literature than this declared-trace model.
- Sparse-attention and KV-serving systems already contain real selectors, paging protocols, kernels, schedulers, and quality/performance studies.

The project-specific contribution that survives is narrower: for complete sequential declared traces with immutable page incarnations, it makes the lifetime frontier, canonical cut accounting, exact weighted-publication recurrence, checker evidence, and a tight factor-two bound for longest feasible reuse explicit in one bounded contract. The written proofs and retained finite checks support that statement.

## Novelty and significance decision

No inspected work was found to state precisely the same combination of serial page-incarnation lives, canonical constant-list epochs, descriptor-publication cost, shortest-path optimality evidence, and the tight longest-reuse bound. That observation supports only a **composition-specific technical note**, not a “first,” “general,” “practical,” or architecture-level novelty claim.

The intended TACO significance gate resolves negatively. The artifact has no authoritative runtime snapshot protocol, concurrent reclamation semantics, refinement from actual kernel loads/masks to declared requirements, native implementation, public serving trace, model-quality study, or measured runtime overhead. Comparable same-venue and adjacent systems do have an executable mechanism and workload connection. Consequently, this project is closed as a reproducible formal boundary study and is **not represented as a submission-ready TACO systems article**.

This is a completed research decision, not an unfinished literature task. Adding the missing runtime and workload layer would change the scientific object and require a new research phase, evidence budget, and evaluation plan.
