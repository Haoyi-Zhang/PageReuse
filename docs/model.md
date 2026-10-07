# Exact model and executable contract

## Scope

The input is a complete declared finite trace, not a log extracted from a serving system. A page incarnation is an immutable symbolic object. Its allocation, initialization, content identity, lifetime, query frontier and dependency specification are assumed to describe the intended abstract execution. The checker checks their internal consistency; it neither authenticates these declarations nor observes actual memory or a GPU kernel. There is no inference of attention quality from addresses.

Queries complete sequentially before the next query begins. Each epoch publishes one constant list of page incarnations. At each step the abstract launch reads the initialized lanes of each selected page that pass that step's declared causal prefix mask. This is the execution semantics, not a verified description of an existing CUDA kernel. Extra causal reads are allowed and can change numerical attention results.

Logical identifiers are dictionary keys, not a proof that token ranges constitute a particular model's KV cache. A binding's KV-group annotation must agree with its page; the checker does not establish a neural architecture's head-to-group function. Symbolic content identities are not hashes of tensor values. Both qualifications matter when translating an external runtime to this schema.

## JSON input

Exactly seven top-level keys are admitted: `pages`, `steps`, `setup`, `visit_weight`, `page_size`, `address_bits`, `heads`. Unknown keys, duplicate JSON object keys, nonfinite numeric constants and booleans in integer fields are rejected. CLI readers consume at most 4 MiB plus one sentinel byte per JSON file, rejecting larger inputs. Strict JSON and object-schema rejection is the checker's responsibility; the untrusted producer is not a substitute for admission. Both CLI readers enforce the file byte bound. The Python JSON parser and interpreter remain trusted. Already decoded in-process objects are outside this file-reader byte bound.

The trace has 1--64 steps, 1--256 page incarnations, and 1--32 query heads. `setup` and `visit_weight` are integers in [0, 2^20]. `page_size` is an integer in [1,128], and `address_bits` is in [1,64]. The publication objective uses `visit_weight=0`; positive values select the explicitly separate visit-sensitive objective.

Each page is an object with exactly these fields:

| Field | Contract |
|---|---|
| `slot` | Integer 0--255; a storage slot, not an incarnation identity. |
| `generation` | Integer 1--2^31-1; strictly increasing over successive lives in the same slot. |
| `content` | Integer 0--2^31-1; immutable symbolic content identity. |
| `format` | `fp16` or `int8`, with abstract element width 2 or 1 byte. |
| `kv_group` | Integer 0--31; compared with binding and descriptor annotations. |
| `first`, `last` | Closed contiguous lifetime with 0 <= first <= last < T. |
| `base` | Integer 0--2^31-1; declared global token coordinate of lane zero. |
| `length` | Integer 1--page_size; all these abstract lanes are initialized at birth. |
| `weight` | Positive integer <=2^20; abstract publication cost, not measured latency. |

Page index `p` in the array is already an incarnation-specific identity. Redundant generation/content/layout fields make mismatch checks explicit; no information-theoretic necessity is claimed for this exact encoding. Within a slot, lives are disjoint and generation numbers strictly increase in chronological order. Different slots have fixed stride `2*page_size`; the largest address end is `slot*2*page_size + length*width(format)`, which must not exceed `2^address_bits`. This models one abstract lane array, not the full multidimensional layout or quantization-scale storage of a deployed attention kernel.

A step contains exactly `frontier`, `bindings`, `nodes`, `roots`. The frontier is an integer in [0,2^31-1]. It need not be monotone: the proof is relative to each declared value, and does not certify that the declarations are genuine autoregressive positions. A binding is the six-element array `[head, logical, p, content, format, kv_group]`. Head and logical identifiers must be in range (logical 0--255), `(head,logical)` must be unique at a step, the page must be live then, and annotations must equal the page metadata. Multiple bindings may alias the exact same incarnation.

A dependency node has exactly `children` and `atoms`. Children and roots are valid node indices. Each atom is `[head,logical,lo,hi]` with a valid binding and a nonempty initialized interval `0 <= lo < hi <= length`. Nodes may contain cycles. Every node and atom must be structurally well typed, including unreachable nodes. All atoms reachable from a root are mandatory (AND dependencies); there are no alternative representations or OR choices. Only reachable atoms are required to satisfy `hi <= cap_t(p)`, where

```
cap_t(p) = min(length_p, max(0, frontier_t - base_p + 1)).
```

The required set R_t is the image of those reachable atoms in physical incarnation indices. Duplication of atoms or aliases does not duplicate the requirement. The graph may be arbitrary, cyclic, interval-shaped, or laminar; its topology does not create a page-choice optimization problem under these mandatory semantics.

The admitted aggregate has at most 2,048 dependency child/read edges, 2,048 nodes, and 8,192 bindings. A step has at most 512 bindings and at most 2,048 root entries. Root entries are included in graph-processing complexity; they are not mislabeled as child/read edges. The finite experiment does not claim to reach every simultaneous dimensional maximum.

## Epochs and costs

For [s,t], U(s,t) is the union of R_q for s <= q <= t. A list S is valid for this epoch exactly when U(s,t) is a subset of S and every incarnation in S lives throughout [s,t]. The canonical list is U(s,t). Its positive weights make it the unique least-weight list for a fixed feasible epoch; an optimal partition need not be unique.

At `visit_weight=0`, c(s,t) = setup + sum(weight_p for p in U). This is a weighted descriptor-publication objective. It does not count actual selector instructions, cache misses, transfer bytes, GPU operations or runtime. The sensitivity objective is

```
c_rho(s,t) = setup + (1 + rho*(t-s+1))*sum(weight_p for p in U).
```

The unweighted page-visit metric is `(t-s+1)*len(U)` per epoch. The sensitivity objective instead uses weighted visits. Neither is a measurement of a serving stack. The fast last-use producer applies only at rho=0. Other rho values use direct dynamic programming.

A partition must cover all T steps exactly once, in increasing contiguous epochs. Empty required sets are allowed; an empty list still incurs the setup charge. Every single-step canonical epoch is feasible for a well-formed trace.

## Certificate and verdict

The exact certificate keys are `epochs`, `potentials`, `frontiers`, `total_cost`. A descriptor is `[p,slot,generation,content,format,kv_group]`. Descriptors must appear in strictly increasing page-index order. Each epoch has `start`, `end`, `pages`, `cost`. The copied `frontiers` must exactly match the trusted input frontier values. They are not the producer's internal lifetime frontier.

There are T+1 nonnegative integral potentials d, with d[0]=0. The checker directly enumerates every interval, computes its canonical union and life feasibility, and for each feasible interval checks

```
d[t+1] <= d[s] + c_rho(s,t).
```

It checks canonical selected lists, exact arithmetic, and `total_cost=d[T]`. Telescoping these inequalities along any alternative valid partition certifies a global lower bound matching the selected plan. No producer helper, lifetime-frontier recurrence, range tree or parent array is imported by the checker. The two programs were nevertheless developed in the same development process; source separation is not an independent-team or independently verified theorem claim.

The executable cost bound is

```
B = T*(setup + (1 + rho*T)*sum(all page weights)).
```

All admitted costs and potentials are <=B; the maximum admitted B is less than 2^61. Python arbitrary-precision integers avoid arithmetic overflow. A port must preserve the inequality directions, inclusive lifetimes, exclusive upper lane bounds, and the pre-arithmetic width checks.

`--safety-only` omits canonical-minimum and dual-optimality obligations but keeps the common certificate shape, descriptor validation, lifetime, coverage, masks and exact stated cost. It is not an optimality verdict. A rejected input returns a deterministic error category and location, not a claim that the proposed schedule is a counterexample to an actual runtime.

## Native sequential realization

`native/allocator.cpp` implements the boundary rule in real C++ heap storage.
Abstract address offsets map to `arena_base + offset`; the declared address
width is not a claim about the host pointer width. Slot activation initializes
all lanes before installation, and every query consults its generation/lease,
checks initialization and extent, and executes exactly the selected causal
prefix loads. The existing nonnegative frontier domain is unchanged.

The matched computation returns actual raw values for unique mandatory atom
lanes. Extra legal prefix loads remain real but do not enter that output vector;
this is not numerical attention equivalence. The written refinement and
source-separated observation checks are in `native/README.md`; all measured
overhead phases and regressions are in `results/native-campaign/`.

## Excluded execution behavior

The native adapter executes CPU memory instructions for this controlled buffer.
It does not execute asynchronous DMA, concurrent allocation or reclamation,
mutable live pages, copy-on-write, tensor arithmetic, actual head dimensions,
quantization scales, speculative decoding, GPU attention, model quality or a
production scheduler. Deployment still requires authority and ordering
arguments for the actual external runtime, and invalidation after every relevant
change; the local refinement does not establish them.
