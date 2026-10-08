# Native CPU campaign

This retained campaign measures the pre-index incremental backward producer on
the declared fourteen synthetic CPU workloads. The C++ slot-buffer execution, requirement sets,
lifetime constraints and publication objective are unchanged. Fresh and
certified publication return identical mandatory-lane values; the reused
list can cause extra legal prefix loads.

The campaign retains eleven alternating pairs per case: 308 raw samples and
154 paired comparisons. Planning/checking and native execution each repeat
eight times per timed sample. Allocation/materialization and the separately
timed complete-path replay each run once; complete-path ticks are not divided
by eight. Two warmup pairs
precede each case. The environment records Intel Core i7-12700KF, one pinned
logical CPU, Windows x64, Zig 0.15.2/C++17 -O2, PowerShell 7.6.5 and .NET
10.0.11. Complete-path medians are 1.037--1.245 times fresh publication;
138 complete-path pairs and 103 native-execution pairs are slower. Local
planner optimization is not a demonstrated serving speedup.

Files include complete compressed samples and native observations, all 207
conformance records, 400 mutation rejection records, summaries of all seven
phases, actual value vectors, and environment/source bindings. Exact
compressed and decoded sizes are in `environment.json`. The 741951
observation events cover 36 groups. No executable DLL or compiler cache is
distributed.

From the artifact directory:

```sh
python -B native/check_saved.py results/native-campaign --measured-source-root results/native-campaign/measured-source
```

This recomputes saved-data arithmetic and validates complete records with the
original Python checker. Explicit source selection verifies all seven recorded
hashes against the byte-identical originals in `measured-source`; those archived
sources are not executed. To use the uncompressed checker interfaces,
decompress copies into a separate working directory. Native reproduction
commands are in `native/README.md`. The two additional complete planner
comparison repetitions are in `results/native-comparison`; they do not
replace this declared phase campaign.
