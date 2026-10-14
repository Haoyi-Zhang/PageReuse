# Sequential device conformance

These records come from actual CUDA Driver API execution on the device identified
in `summary.json`. Fresh and exact publication replay all 200 frozen traces and
seven existing native controls. Every plan passes the original source-separated
checker; fresh has the safety contract and exact also has the optimality contract.

The adapter keeps one guarded device byte arena. At each boundary it retires
expired occupants, transfers fully initialized birth payloads into their slots,
then installs resident page/generation/width/length metadata. Descriptors transfer
at epoch starts and remain until refresh. A PTX kernel validates resident metadata
before computing the causal prefix, including at zero caps, and performs actual
one- or two-byte global loads. Synchronization and full output acquisition precede
the next boundary. Arena bytes and both canaries are checked after every query.
Content/group/lifetime declarations are checked on the host; this adapter supplies
its own immutable payloads and residency.

Each step retains every B-sized output cell, including masked sentinels, the
mandatory-atom projection, and the complete owned negative-control output. The
control changes one resident generation to zero; allocated addresses never change.
That descriptor must be rejected before payload loads, including at zero cap.
The portable consumer checks all stored cells, counts, source and frozen-input
bindings in ordinary and optimized Python.

```sh
python -B native/gpu_pages.py check results/gpu-pages
python -B native/test_gpu_pages.py -v
python -B -O native/test_gpu_pages.py -v
```

Actual device reproduction requires an existing CUDA driver, a little-endian
64-bit host and compute capability 6.1 or later:

```sh
python -B native/gpu_pages.py run /absolute/fresh/output-directory
```

There is no CPU fallback or toolkit installation. The driver JIT-compiles the
included PTX. Hosted CPU CI validates retained records and admission logic; it
does not execute a GPU. This experiment has no performance timers and evaluates
the declared synthetic byte-array semantics. Numerical attention, concurrent
reclamation and production serving require additional models and workloads.

The adapter follows the NVIDIA [Driver API memory-management reference](https://docs.nvidia.com/cuda/cuda-driver-api/group__CUDA__MEM.html)
and [kernel-launch reference](https://docs.nvidia.com/cuda/cuda-driver-api/group__CUDA__EXEC.html).
These are implementation documentation, not peer-reviewed evidence of performance.
