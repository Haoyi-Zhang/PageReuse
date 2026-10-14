# Same-contract complete costs

All 207 existing rho=0 serialized inputs, four exact arms, eight balanced
rotating rounds, 6,624 actual measured C++ calls; 828 warmups are separate.
`samples.jsonl.gz` retains every full wall/CPU observation, its seven nested
phase clocks, actual publication UTF-8, actual mandatory vector, scalar counts
and byte sizes. It is losslessly identical to the original measured stream.

Ordinary exact uses the current incremental planner without transmitted
potentials; its consumer checks the plan and independently recomputes the scalar
optimum. Certified incremental shares that planner, range-min changes producer,
and direct union is a semantic reference. Every arm supplies exact global
optimality and the same native contract. None is a safety-only fresh baseline.

Inputs are byte-bound to `../exact-document-workflow/inputs.jsonl.gz`, not newly
generated workloads. Each call really reads and closes its input and publication
files, admits/plans/serializes/checks, constructs fresh mask/index/arena, executes,
projects/guards/frees and deletes publication. Local OS file APIs are measured;
physical disk traffic, durable flush, RSS, network, GPU and serving are not.

`summary.json` and `independent-summary.json` are complete independently
recomputed science summaries; `phase-costs.csv` sums the actual nested phase
observations; `case-ratios.csv` sorts each arm's input-wise median of eight paired
full-wall ratios to ordinary exact. The latter is plot data, not a new workload
matrix or independent-population estimate. `totals.tex` is generated from full
invocation timers, never by adding separately measured component medians.

Range-min's 2.880237-second wall sum is below ordinary exact's 2.943591, but
range-min is slower on 173/207 input medians; incremental is slower on 129/207,
direct union on 197/207. No unfavorable observation was removed. Coarse process
CPU yields 1,561 zero ordinary full samples; zero denominators remain undefined,
not epsilon-replaced. No precise per-call CPU acceleration claim is supported.

`native-build.json`, `managed-build.json`, `ready.json`, `worker-process.json`
and `startup-build.json` separate real build/startup/envelope costs from calls.
Native compiler main-process CPU is recorded, but subprocess-tree CPU is null.
Scientific source hashes, exact 207-input hashes, runtime hashes and raw-record
hashes are in `environment.json`. Only private run identity/authority hash and
native build paths/argv were omitted on publication; complete private originals
remain preserved. No binary, compiler cache, work status or private audit log
is included. Audit with normal and optimized Python as in `native/README.md`.
