# Native sequential CPU bridge

`allocator.cpp` implements the paper's lane-array execution using a real C++ heap
buffer, recycled physical slots and volatile byte loads. `NativeBridge.cs` is a
Roslyn-compiled .NET harness for bounded JSON admission, direct dynamic
programming, a separate bitmap/potential checker and the C ABI. Python is used
only to independently check recorded results, never as the native executor.
All new code uses the artifact's existing MIT license.

This is a synthetic CPU realization of Sections 2.3--2.4 and Theorem 1, not a
GPU kernel, serving application, numerical attention implementation or online
selector. The direct-DP setup measurements are not timings of the existing
Python last-use range tree. The original inputs, certificates, proofs, numerical
results and integrity mechanisms remain unchanged.

## Trace-to-memory mapping

For one immutable admitted trace, C++ allocates `(max_slot+1)*2B` bytes, plus
32-byte guard regions at either end. A page's byte address is
`arena_base + 2B*slot + width*lane`. Thus the paper's address expression maps to
an offset in a real allocation. `address_bits` bounds that offset, as in the
existing executable; it does not imply that a Windows virtual pointer fits
in the trace's often 16-bit symbolic address space. Native pointers remain
64-bit, and both sides check the allocation extent before any load.

At boundary `t`, C++ retires every page with `last=t-1`, then activates pages
with `first=t`. Activation requires an empty slot and a strictly newer
generation, writes the synthetic bytes of every declared lane, and installs
the resident page/generation and initialized length. Slot padding is poisoned
but never loaded. Pages and masks do not change during a query.

The relation between native and abstract states is:

| Abstract fact | Native representation and check |
| --- | --- |
| `p` is active at `t` | resident slot equals `p`, and `first<=t<=last` |
| generation/content/format/group | immutable page metadata and copied descriptor annotations |
| all declared lanes initialized | completed birth writes and initialized-length record |
| epoch lease `[s,t]` | descriptor lease endpoints contained in the page lifetime; consulted at every query, even when cap is zero |
| abstract address `2B*slot+width*i` | checked relative offset in the C++ buffer |
| load set `L_q(S)` | actual prefix loop `0<=i<min(length,max(0,frontier-base+1))` for every selected descriptor |
| completion before reclaim | synchronous loop returns from query loads before the next boundary |

Induction on boundaries establishes resident-state equality with `Q_t`: only
expired incumbents are removed, then exactly the pages born at that boundary
are installed. Disjoint slot lifetimes make activation unambiguous. Each valid
descriptor therefore names its resident incarnation throughout its lease.
The prefix-loop bounds yield exactly the model's loads, and each native byte
is inside a fully initialized live allocation and satisfies the declared
causal cap. This is a written refinement argument for this adapter, supported
by recorded native observations; it is not a proof-assistant verification or
authentication of an external allocator log.

The current executable trace language admits frontiers in `[0,2^31-1]`.
Both harness and C++ enforce this same range. Nonmonotone frontiers are allowed;
the zero-cap control keeps a leased descriptor live while loading none of its
lanes. Negative frontiers are not inputs to the existing executable language.

## Matched outputs and conservative baseline

The baseline publishes `R_q` afresh at every step. Certified execution publishes
the canonical constant union for each optimal epoch. Both use the same allocator,
synthetic bytes, mask, descriptor validation and native load loop. A reused list
can contain extra pages, so the two complete load sets need not be equal.

The computation being compared returns the raw loaded values for the unique
mandatory `(page,lane)` pairs named by reachable atoms, in sorted order at each
query. Extra prefix loads are executed, recorded and consumed in a running sink
but excluded from this mandatory projection. Each one-/two-byte payload is
`(131*content + 17*generation + 7*group + 29*lane) mod 2^(8*width)`;
two-byte values use little-endian bit assembly. `fp16` names storage width here,
not a floating-point arithmetic experiment. Equality of the mandatory results
does not establish equality of sparse or dense attention outputs.

Correctness checks passed all 200 retained optimal costs, actual byte results
on both native paths, three wider original synthetic workloads, and four
integer/address/empty/zero-cap controls. The all-empty four-step trace runs
both plans, and also calls `nb_run` with an actual null descriptor pointer and
`D=0`. Empty epochs clear the published list without null-pointer arithmetic.
Four benign metadata controls reject stale generation, missing initialization,
invalid extent and expired lease before issuing any invalid native load. The
harness checker also rechecks all 400 original malformed/suboptimal controls.

`check_native.py` uses the unchanged source-separated Python checker on every
new plan, separately reconstructs mandatory values, and streams the complete
native panel/edge observation logs. It checks every retirement, activation,
publication, descriptor consultation, lane value and relative/absolute address
mapping. These checks are source-separated, not independent-team review.

## Mandatory-lane bookkeeping

Arena construction derives ordered mandatory-cell indices from the unchanged
dense mask. C++ builds its indices during the existing mask-admission checks;
the managed bridge builds its projection indices while preparing that mask.
Every replay resets all mandatory scratch cells, checks that each was loaded,
and returns them in the original `(page,lane)` order. Nonmandatory scratch cells
are not returned or used to establish coverage. Selected extra prefix loads,
their sink contributions, resident checks and zero-cap lease checks are unchanged.
Fresh and certified execution use this same implementation.

Index construction and allocation remain inside the complete decoded-trace path,
not in an excluded preprocessing phase. Replay reset and projection visit the
mandatory cells rather than the entire dense grid. Dense mask admission is still
performed. The additional native index payload is at most 8 MiB plus 260 bytes
of step offsets under the existing bounds, excluding vector capacity and allocator
overhead. Managed index arrays and temporary lists also require additional memory.
These complexity bounds alone do not establish a wall-time gain, particularly
for dense masks.

## Reproduction and reserved measurements

Requirements: Windows x64, PowerShell 7 with its existing Roslyn compiler,
Zig 0.15.2 and Python 3.10+. Nothing is installed. Use an existing `zig` on PATH
or give its executable path with `-Zig`. From the artifact directory:

```powershell
./native/bounded.ps1 -Mode Compile -Zig /path/to/zig.exe -WallSeconds 240 -MemoryMiB 2048
./native/bounded.ps1 -Mode Conformance -Zig /path/to/zig.exe -WallSeconds 120 -MemoryMiB 1024
python -B ./native/check_native.py ./results/native-reproduction/conformance
```

After compilation, an explicit additional regression step exercises sparse and
dense projections, all-empty/null lists, recycled slots, zero-cap resident
checking, repeated replay with a missing mandatory load, and the native ABI's
maximum configuration axes using owned benign arrays:

```sh
python -B native/test_mandatory_projection.py --library /path/to/owned/p054_allocator.dll -v
```

The seven tests require only Python's standard library and a locally compiled
native library; a compatible `.so` path is also accepted by the test interface.
They are separate from the 207-case conformance route and 400 retained checker
controls, and remain separate from those counts. The current Windows hosted
workflow configures this step; configuration alone is not execution evidence. The
recorded finite checks used one CPU, 90 seconds and 512 MiB.

The default work root is `artifact/results/native-reproduction`; `-WorkRoot`
selects another root and `-OutDir` a new empty subdirectory. Compiler caches and
temporary files stay in that selected root. Scientific execution is pinned to
one logical CPU by the bounded launcher. Full raw observations are streamed;
the native arena is at most 64 KiB, native scratch at most 8 MiB. An external
caller should also bound the independent Python audit (90 seconds and 512 MiB
were used for the recorded audit).

`protocol.json` declares the 14-case workload panel, 11 alternating-order pairs,
eight complete trace replays per timed block and two untimed warmup pairs.
Measurement is an explicit separate branch requiring `-SlotId`. **Do not invoke
that branch without the coordinator's assigned exclusive slot.** It validates
the source and binary hashes against completed conformance and the independent
audit before calling any performance timer:

```powershell
./native/bounded.ps1 -Mode Measure -Zig /path/to/zig.exe -SlotId ASSIGNED_SLOT -WallSeconds 120 -MemoryMiB 1024
python -B ./native/summarize_native.py ./results/native-reproduction/measure
```

Separate raw fields record planner setup, certificate checking, allocation,
descriptor materialization, native execution and the managed call/projection
envelope. An additional complete path from an already decoded trace is actually
timed; it is not a sum of phase estimates. JSON decoding, compilation, result
verification and serialization are outside these timers. Every sample retains
the actual mandatory values and native load/byte/publication counts. The
summary preserves every paired ratio, slowdown and negative gain. The retained
run predates the mandatory-index change and is in `../results/native-campaign/`:
all 308 samples and 154 paired comparisons
are present. Certification is slower in 103 native-execution comparisons and
138 complete-path comparisons; all 14 complete-path paired medians are above
one (1.037--1.245). The wide-rotate case retains its 32-fold increase in actual
lane loads. Small near-parity differences are not a stable-speedup claim.

`Produce` uses incremental backward unions; `ProduceReference` implements the
direct-union semantic comparator. `compare.ps1` checks full certificate
agreement on 207 cases and measures both plus fresh publication on the same
fourteen inputs. `summarize_comparison.py` recomputes each paired ratio.
Both repetitions, including all 756 samples, are retained under
`results/native-comparison`; these measurements also predate the mandatory-index
change. The proof is `proofs/native-planning.md`.

## Published evidence without execution

From the artifact directory:

```sh
python -B native/check_saved.py results/native-campaign --measured-source-root results/native-campaign/measured-source
```

This saved-data checker reads the full `.gz` evidence, verifies functional
source/data bindings, checks the plans and all 308 actual value/count records,
and recomputes paired arithmetic without compilation, native execution or
timing. It was added after measurement; the seven measured source files remain
bound to their recorded hashes. `results/native-campaign/measured-source` retains
all seven original files, copied byte-for-byte from the pre-change sources.
`--measured-source-root` selects that directory for hashing and reads its verified
protocol; it does not import, compile or execute those files. The option changes
neither the original hashes nor the data/value/count/paired-arithmetic checks.
Without it, the checker still uses `artifact/native` and rejects changed measured
sources. This is verification of historical evidence, not certification of a
changed executable. `protocol.json` remains the frozen premeasurement declaration.

The portable routing controls are a separate explicit step:

```sh
python -B native/test_saved_routing.py -v
```

They check all seven bindings and selected protocol, each altered or missing
source, incomplete/extra manifests and a non-directory root using inert local
fixtures. These five tests do not execute native code and are not part of the
unchanged 207/400 conformance counts. They are configured in the current Linux
hosted workflow; its presence is not a test-pass record.

The complete observation record retains 741951 events; exact compressed and
uncompressed sizes are recorded in its environment metadata. No records were removed.
See the campaign README for decompression before `check_native.py` or
`summarize_native.py`, whose uncompressed interfaces are unchanged. The public
environment omits machine paths and coordination identifiers; no executable
library, PDB or compiler cache is distributed.

All measurements are synthetic single-host CPU evidence. Abstract publication
weights are not fitted to runtime. Concurrent allocation, external-trace
authentication, device execution, neural quality, public serving workloads
and production applicability remain outside this bridge.

## Current-source five-policy functional comparison

`NativePolicies.cs` adds longest-feasible reuse, anchored four-step reuse, and
a C# port of `src/producer.py`'s rho=0 last-occurrence/range-add/range-min kernel.
The tree preserves earliest-start ties, point replacement, lazy additions,
expiry buckets and the persistent birth frontier. It returns full epochs and
prefix potentials, not just the optimal cost. It rejects nonzero rho rather than
silently calling a different algorithm. The direct-union reference and incremental
backward DP remain available under their original names and implementations.

The five arms are fresh, longest-feasible, four-step, exact rho=0 range-min, and
exact rho=1 incremental DP. Price 1 is fixed, not fitted to loads or time. The
four-step cap is the next multiple-of-four boundary even after an earlier
lifetime cut. All arms use `ReplayPolicy`: price/plan/check, mask and mandatory
index construction, allocation, descriptor materialization, native execution,
mandatory projection, guard checks and free. No plan, index or arena is reused
between arms. Future complete-path timing must charge this entire path.
Heuristics call safety checking only and never solve a DP to supply potentials;
the exported safety-checker JSON has zero placeholders solely for its existing
schema. Exact arms retain the full optimality checker. Thus their certification
costs differ intentionally.

`policies.ps1` is a bounded, single-CPU functional driver with **no timing branch**.
It compiles the three current C# files to a private `policy_bridge.dll`, checks
the allocator source/binary against a real Compile manifest, and records source,
input, saved-certificate, managed/native binary and output-record SHA-256 bindings.
Only JSON / losslessly gzip-compressed JSONL evidence is retained in the stable `results/native-policy-comparison`
directory. Binaries, compiler/runtime caches and worker logs remain in an explicit
private work directory outside this artifact-root repository. The driver rejects
in-repository build/runtime paths and refuses an existing result directory.
An explicit private `-OutDir` (for example in `RUNNER_TEMP`) is supported for CI
reproduction; the public dataset path remains stable.
To reproduce from `artifact/` with an
existing Zig compiler (a matching previously compiled current allocator may
also be reused):

```powershell
$private = '/absolute/path/outside/artifact'
./native/bounded.ps1 -Mode Compile -Zig /path/to/zig.exe -WorkRoot "$private/native-build" -WallSeconds 240 -MemoryMiB 2048
./native/policies.ps1 -Library "$private/native-build/build/p054_allocator.dll" -BuildEnvironment "$private/native-build/compile/environment.json" -WorkRoot "$private/policy-runtime" -WallSeconds 120 -MemoryMiB 1024
python -B ./native/check_policies.py ./results/native-policy-comparison --library "$private/native-build/build/p054_allocator.dll" --managed-assembly "$private/policy-runtime/policy_bridge.dll" --build-environment "$private/native-build/compile/environment.json"
```

The driver records 200 original cases plus three wide workloads and four edge
controls, with five executions per case (1,035 total). `cases.jsonl.gz` retains
the original graphs, strata and declared prices. Full-certificate gates compare
direct/incremental on all 207 original inputs, all three exact planners on all
207 explicitly repriced rho=0 inputs, and direct/incremental on all 207 repriced
rho=1 inputs. The max-cost edge declares nonzero rho; its rho=0 gate is explicitly
a repriced control, not evidence that the range tree implements arbitrary rho.
The 200 saved certificates are also compared in full. `NativePolicyTests.cs`
adds 134 finite policy controls and primitive tree tests, including empty and
repeated-page ties, unused expiry, persistent birth and off-anchor lifetime cuts.
The equivalence gates and paired-optimum calculations are outside `ReplayPolicy`
and must remain outside every future per-arm complete-path timer.

`check_policies.py` independently checks every plan using the unchanged Python
producer specification and source-separated checker, reconstructs every mandatory
value and native count/sink, and verifies the bindings. Its `independent-summary.json`
separates the full 200 from the seven native controls and reports every original
stratum plus the 48 tiny / 8 tight-family / 104 regular / 24 medium / 12 large /
4 boundary families. Publication accounting and the fixed-price objective have
separate paired optima and above-optimum counts; weighted visits are not bytes.
All five policies were valid on all 200 in the current functional run. Publication
cost was above the rho=0 optimum on 175 fresh, 26 longest-feasible, 104 four-step,
zero range-min and 93 rho=1-exact cases. The last arm instead reaches the rho=1
optimum on all 200. Synthetic stratum frequencies do not estimate serving use.

A portable saved-record check needs no binary distribution or native execution:

```sh
python -B ./native/check_policies.py ./results/native-policy-comparison --verify-only
```

It recomputes the saved summary, plans, values, counts and source/data bindings;
it explicitly reports `binary_files_checked=false`. Supplying all three private
binary/build paths additionally verifies the actual recorded runtime files.
The three large record files are `cases.jsonl.gz`, `planner-agreement.jsonl.gz`
and `policies.jsonl.gz`. Their compressed and complete decompressed identities
are recorded; all rows and mandatory vectors are retained. The transparent
reader caps bytes actually decompressed at 256 MiB, not compressed file size.

This functional route does not call `Measure`, `ComparePlanners`, `Batch` or
`nb_batch`. It provides no current timing, speedup, GPU or deployment result.
Historical campaigns, their original measured sources, protocol and unfavorable
results are unchanged. A separately authorized timing slot is still required.

## Evidence admission and serialized-input workflow

The current native auditors, historical arithmetic summarizers, ABI-size check
and tiny oracle use explicit scientific gates that remain active under `-O`.
`evidence.py` distinguishes integers from booleans/floats and rejects duplicate
keys/nonfinite numbers in the repaired record readers. This does not certify
every other driver under optimization or change archived measured sources.
`check_saved.py` prints without rewriting retained data; its optional
`--output-summary` creates a new file. `check_native.py --verify-only` compares
its existing summary without rewriting it.

```sh
python -B native/test_evidence.py -v
python -B -O native/test_evidence.py -v
python -B -O native/test_saved_routing.py -v
```

`NativeWorkflow.cs` compares direct-union, incremental-backward and range-min
exact planners under the same rho=0 objective and full optimality contract.
Each arm independently acquires the same memory-resident UTF-8 bytes, decodes
and admits the original graph, plans, serializes a full certificate, then
decodes/strictly checks the consumed certificate, builds masks/indices,
allocates/materializes, executes C++ loads, projects results, checks guards and
frees the arena. No decoded trace, plan, mask, index or arena is shared across
arms. Original input graphs are not reconstructed from normalized requirements.

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
./native/workflow.ps1 -Library "$private/native-build/build/p054_allocator.dll" -BuildEnvironment "$private/native-build/compile/environment.json" -WorkRoot "$private/document-runtime" -OutDir "$private/document-records"
python -B native/check_workflow.py "$private/document-records"
python -B -O native/check_workflow.py "$private/document-records"
```

The worker is pinned to one logical CPU, with a default 120-second deadline
and 1024 MiB working-set threshold polled every 250 ms, not an OS-enforced quota.
Runtime files remain in the explicit private work root. The public
`results/exact-document-workflow` retains all 207 inputs and 621 actual native
rows, environment and source/input/binary/record bindings. Lossless gzip streams
include their complete decoded identities. `check_workflow.py` accepts plain or
gzip evidence and checks full certificates, native values/counts/sink and bytes
against source-separated Python specifications, without executing native code.
Normal/optimized audits are repeated checks, not additional native executions.

Across all three arms, 4,067,544 input bytes are acquired and 912,579 certificate
bytes consumed. These counts are serialized work, not latency, peak memory,
independent workloads or deployment. This functional workflow invokes no
performance clock or warmup. It is unchanged; the distinct, explicitly
authorized complete-cost protocol below supplies local-file timings.

## Same-contract complete costs

`NativeCompleteCost.cs` and `complete_cost.ps1` measure four full paths on the
same 207 frozen serialized rho=0 inputs, without changing bounds or guarantees:

- `ordinary-exact`: incremental producer; epochs/frontiers/cost only on the
  wire; consumer checks safety/cost and independently recomputes the scalar
  optimum via backward bitmap unions. No transmitted potentials or redundant
  optimal-plan construction is charged to this consumer.
- `certified-incremental`: the same producer plus full potentials and strict
  certificate checking.
- `certified-range-min`: range-min producer with the identical strict consumer.
- `certified-direct-union`: slower direct-union semantic reference, not the
  closest ordinary baseline.

Each of eight rounds rotates four positions, giving two full position cycles
and 6,624 actual full calls (1,656 per arm). One instrumented warmup per input/arm
adds 828 native executions, excluded from the statistics. Every call independently
reads/closes the same UTF-8 file, decodes/admits, plans, serializes, writes/closes
publication, reads/closes/parses/validates it, constructs masks/index, allocates,
materializes, calls C++ `nb_run`, projects, checks guards, frees and deletes the
publication file. Seven nested phase clocks are inside one enclosing invocation
timer; complete totals are not sums of phase medians. Exact native vectors,
counts and actual published UTF-8 are retained for every measured call.

The public evidence is `results/complete-cost/`: `samples.jsonl.gz`, protocol,
completion, environment and build/startup records; complete independent summaries;
phase CSV, sorted case-ratio CSV and generated TeX table. Inputs are the unchanged
`results/exact-document-workflow/inputs.jsonl.gz`, bound byte-for-byte by all 207
hashes. `check_complete_cost.py` uses source-separated Python semantics to check
every actual publication, optimum, vector, count, byte total, clock schema and
fixed call/order schedule. Scientific gates do not use bare Python `assert`.

```sh
python -B native/check_complete_cost.py results/complete-cost
python -B -O native/check_complete_cost.py results/complete-cost
python -B native/test_complete_cost.py -v
python -B -O native/test_complete_cost.py -v
python -B native/summarize_complete_cost.py results/complete-cost /new/private/table-output
```

Actual measured sums (wall / process CPU seconds) are ordinary 2.943591 / 1.515625,
certified incremental 3.023164 / 1.953125, range-min 2.880237 / 1.390625, and direct
union 9.740259 / 5.156250. Certified arms are slower on 129, 173 and 197 of 207
paired input medians respectively. All slowdowns and zeros remain. CPU uses
Windows `GetProcessTimes` kernel+user totals, including runtime threads; 100-ns
units are coarse accounting, not 100-ns resolution. Full CPU zeros number 1,561,
1,538, 1,567 and 1,446 per 1,656 calls. Zero-denominator CPU ratios are null, never
epsilon-adjusted. Phase wall/CPU clocks and exact-zero counts are in `phase-costs.csv`.
No outlier filtering, fitted price, repeat-until-gain or forced GC is used.

Fresh private Zig caches: native build/link 14.217555 wall seconds, compiler main
process CPU 11.906250 seconds; full compiler subprocess-tree CPU is unavailable.
Managed compile: 0.630521 wall / 0.671875 process CPU seconds. Worker launch through
readiness (checks and native/managed load included): 1.267050 wall / 0.406250 CPU.
Whole-worker envelope: 25.946230 observed wall / 12.906250 CPU, including warmups,
validation and compression, not a per-call total. Do not add these different
scopes or replace the enclosing clocks with phase sums.

Reproduction requires existing Windows x64 PowerShell/Roslyn, the owned current
allocator DLL and its matching real build manifest, plus private materialization
of each `input_utf8` exactly as `<id>.json` and an `index.jsonl` in frozen order.
`manifest.json` records `files` (207 filename/hash pairs), `frozen_inputs_sha256`,
`index_sha256`, `input_count` and `input_bytes`. Materialization is reproducible
without generating any new trace:

```sh
python -B native/prepare_complete_cost.py /private/serialized-inputs
```

It copies each frozen `input_utf8` losslessly and writes the complete index and
manifest; it refuses an existing output or an in-artifact runtime directory.
Use a fresh private WorkRoot/OutDir:

```powershell
./native/complete_cost.ps1 -Authority /private/authority.json -Inputs /private/serialized-inputs -Library /private/p054_allocator.dll -BuildEnvironment /private/native-build.json -WorkRoot /private/new-runtime -OutDir /private/new-measurement
```

The authority file must explicitly state `project_id="P054"`,
`authority_kind="explicit-user-resume"`, `complete_cost_measurement_authorized=true`,
the actual request and a run identity. This separate protocol rejects CI and
does not invent or reuse a historical reserved SlotId. Existing reserved-slot
drivers/gates are untouched. Source/input/native/managed hashes are checked;
runtime files, authority text, compiler caches and process audit logs remain private.
The bounded worker uses affinity 1, 180s and a 1024 MiB threshold polled every
200ms, not an OS memory quota.

Local-file read/write/close costs include OS API/cache behavior. No explicit
durable flush or physical I/O measurement is made; RSS, disk/network bytes,
GPU and serving costs are null/unavailable, not zero. No CPU timing ratio or
deployment gain is guaranteed. Technical timer semantics are documented by
[Microsoft GetProcessTimes](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getprocesstimes)
and [Stopwatch](https://learn.microsoft.com/en-us/dotnet/api/system.diagnostics.stopwatch).
