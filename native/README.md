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

## Reproduction and reserved measurements

Requirements: Windows x64, PowerShell 7 with its existing Roslyn compiler,
Zig 0.15.2 and Python 3.10+. Nothing is installed. Use an existing `zig` on PATH
or give its executable path with `-Zig`. From the artifact directory:

```powershell
./native/bounded.ps1 -Mode Compile -Zig /path/to/zig.exe -WallSeconds 240 -MemoryMiB 2048
./native/bounded.ps1 -Mode Conformance -Zig /path/to/zig.exe -WallSeconds 120 -MemoryMiB 1024
python -B ./native/check_native.py ./results/native-reproduction/conformance
```

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
run is in `../results/native-campaign/`: all 308 samples and 154 paired comparisons
are present. Certification is slower in 109 native-execution comparisons and
151 complete-path comparisons; all 14 complete-path paired medians are above
one (1.672--121.481). The wide-rotate case retains its 32-fold increase in actual
lane loads. Small near-parity differences are not a stable-speedup claim.

## Published evidence without execution

From the artifact directory:

```sh
python -B native/check_saved.py results/native-campaign
```

This saved-data checker reads the full `.gz` evidence, verifies functional
source/data bindings, checks the plans and all 308 actual value/count records,
and recomputes paired arithmetic without compilation, native execution or
timing. It was added after measurement; the seven measured source files remain
unchanged. `protocol.json` remains the frozen premeasurement declaration.

The complete observation record compresses from 148129303 to 9627054 bytes;
the raw samples compress from 15213670 to 814804 bytes. No records were removed.
See the campaign README for decompression before `check_native.py` or
`summarize_native.py`, whose uncompressed interfaces are unchanged. The public
environment omits machine paths and coordination identifiers; no executable
library, PDB or compiler cache is distributed.

All measurements are synthetic single-host CPU evidence. Abstract publication
weights are not fitted to runtime. Concurrent allocation, external-trace
authentication, device execution, neural quality, public serving workloads
and production applicability remain outside this bridge.
