# Exact serialized-input CPU workflow

The dataset contains the fixed 200 retained traces and seven separately labeled
native controls, explicitly repriced to rho=0. It is not a new workload sample.
Each of direct-union DP, incremental-backward DP and range-min planning
independently consumes identical serialized input bytes and produces the full
optimality contract. Every certificate is serialized, parsed and strictly
checked before its consumed plan drives the C++ allocator and actual byte loads.

All 621 execution rows retain the full certificate, actual mandatory value
vectors, native load/byte/publication/copy counts and sink. All three arms
agree in full on each input. Total acquired input bytes are 4,067,544 and total
consumed certificate bytes are 912,579, counting all three arms. They are not
timing or peak-memory measurements. Disk/network acquisition is not exercised.
There is no GPU, neural attention, online serving or deployment result.

- `inputs.jsonl.gz`: original graph/binding/alias context and exact input UTF-8
  string, with suite and stratum retained.
- `executions.jsonl.gz`: all 621 actual native execution rows, without filtering.
- `summary.json`: native functional completion record.
- `environment.json`: actual CPU/OS/runtime/compiler, eight literal source
  bindings, original corpus and private binary hashes, record hashes and full
  decoded identities. Publication only losslessly gzip-encodes the two streams;
  their original raw hashes and environment identity are retained.
- `independent-summary.json`: source-separated certificate/value/count/byte
  reconstruction. Verification does not rerun native code.

From `artifact/`, with `PYTHONDONTWRITEBYTECODE=1`:

```sh
python -B native/check_workflow.py results/exact-document-workflow
python -B -O native/check_workflow.py results/exact-document-workflow
```

Executable/runtime files are not distributed. A fresh native reproduction uses
the existing compiler and the bounded functional `native/workflow.ps1` route in
`native/README.md`. Source separation is not independent-team or mechanized
verification. Current same-guarantee elapsed/maintenance/acquisition costs
remain a separate measurement obligation; older decoded-input timings do not
measure this serialized path. All historical campaigns remain unchanged.
