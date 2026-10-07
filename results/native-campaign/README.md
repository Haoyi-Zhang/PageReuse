# Native CPU campaign

This campaign executes the paper's sequential lane-array contract in a real
C++ slot buffer. It does not execute GPU attention or a production service.
The conservative fresh-list and certified-list paths share allocation,
initialization, resident checks, masks and byte-load code. Both return the same
ordered mandatory-lane values; legal extra prefix loads are separately counted.

The frozen panel has 14 cases, 11 alternating-order pairs per case and eight
complete trace replays per timed block. All **308 samples / 154 comparisons**
are retained. Two untimed warmup pairs precede each case. The measured system
was Windows x64 on an Intel Core i7-12700KF, pinned to one logical CPU, using
Zig 0.15.2/C++17 `-O2`, PowerShell 7.6.5 and .NET 10.0.11. The worker had a
120-second wall deadline and a 1024-MiB working-set threshold.

Results are deliberately not presented as a serving speedup. Native execution
is slower in 109/154 comparisons. The full path from an already decoded input
is slower in 151/154 comparisons and in every case's paired median, with
ratios 1.672--121.481. The transparent C# direct-DP setup dominates the largest
cases; these are not timings of the original Python range-tree implementation.
Wide rotate performs 262144 certified lane loads versus 8192 fresh loads despite
reducing publications from 64 to one. All negative gains and near-parity cases
remain in the raw data and summaries.

## Files

| File | Content |
| --- | --- |
| `samples.jsonl.gz` | Complete 308 raw timing samples, actual value vectors and counts; lossless compression of 15,213,670 bytes to 814,804 bytes |
| `observations.jsonl.gz` | Complete 741,951 native transition/lease/address/load events in 36 groups; lossless compression of 148,129,303 bytes to 9,627,054 bytes |
| `summary.json` | All paired ratios, median/min/max, slower-pair counts and phase summaries |
| `phases.csv` | Readable 14-case × seven-phase table; includes regressions |
| `conformance.jsonl` | All 207 native correctness records, new plans and actual mandatory outputs |
| `conformance-summary.json` | Original 200 optimum matches, 400 rejected checker controls, four native metadata controls and null-descriptor all-empty test |
| `native-checker-mutants.jsonl` | All 400 checker rejection records |
| `observation-checker-summary.json` | Completed source-separated audit of the native observations |
| `checker-summary.json` | Saved-data audit of full compressed evidence, source bindings and all 154 paired outputs/counts |
| `environment.json` | Path-redacted environment, functional source bindings and lossless-compression hashes consumed by the saved-data checker |

The 11 retained identifiers and three wider synthetic rules are specified in
`../../native/protocol.json`. Its premeasurement status is kept unchanged as a
frozen declaration; `summary.json` reports the completed run. Historical Python
results and resource accounting are separate and unchanged.

## Check without execution

From the artifact directory:

```sh
python -B native/check_saved.py results/native-campaign
```

This reads `.gz` directly and verifies both compressed and decompressed content,
the seven measured source versions, the original input/certificate versions,
every new plan with the unchanged checker, all actual mandatory values/counts,
sample ordering and paired arithmetic. It runs no compiler, allocator or timer.
`native/check_saved.py` is a postmeasurement saved-data checker, not one of the
seven measured source files.

For the original uncompressed observation-audit and summarization interfaces,
first decompress the two complete records to a selected working directory.
For example, from this directory:

```sh
python -c "import gzip,shutil; src=gzip.open('observations.jsonl.gz','rb'); dst=open('observations.jsonl','wb'); shutil.copyfileobj(src,dst); dst.close(); src.close()"
python -c "import gzip,shutil; src=gzip.open('samples.jsonl.gz','rb'); dst=open('samples.jsonl','wb'); shutil.copyfileobj(src,dst); dst.close(); src.close()"
```

Then, from the artifact directory:

```sh
python -B native/check_native.py results/native-campaign
python -B native/summarize_native.py results/native-campaign
```

Fresh native conformance still generates and audits **uncompressed** working
files. See `../../native/README.md` for the public parameterized reproduction
entry points. Performance runs require an explicitly allocated exclusive slot;
do not substitute uncontrolled concurrent timings for this retained campaign.

No executable library, PDB, compiler cache, private command, machine path or
credential is distributed here. The complete private raw evidence was retained;
the published `.gz` files remove no scientific records.
