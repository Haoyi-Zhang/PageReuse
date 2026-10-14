# Incremental backward union planning

The native producer computes the same prefix recurrence and visit-priced
objective as the manuscript. For a fixed right endpoint t, scan starts s from
t down to zero. Maintain the union of required pages seen so far, its weight,
the largest birth step, and the smallest expiry step. Before evaluating s,
insert exactly the newly encountered pages in R_s. Induction over decreasing s
gives exactly U(s,t), its weight, and its lifetime intersection.

If the largest birth exceeds s or the smallest expiry precedes t, [s,t] is
infeasible. Decreasing s further cannot remove an already included page,
decrease the largest birth, or increase the smallest expiry. All earlier starts
are therefore also infeasible and the scan may stop. Otherwise the candidate
cost is D[s]+setup+(1+rho*(t-s+1))*weight. This equals the direct union method's
candidate, so taking its minimum implements the identical recurrence. Equal
costs choose the earliest start in both implementations. Backtracking and
sorted canonical union materialization consequently give identical epochs,
potentials and costs, not just equal optimum values.

Let I be the number of required-page incidences and P the page count. Across
right endpoints the loop does at most O(T*I) incidence visits, O(T^2) candidate
evaluations and O(T*P) bitmap initialization, using O(T+P) working space beyond
input and output. Backtracking adds canonical-list/output construction. This
bound is for the native backward DP, including rho>0, not the Python rho=0
range-add scheduling kernel.

The direct-union implementation remains a semantic benchmark called
ProduceReference, not an alternative delivered revision. The current producer
uses incremental unions. The unchanged native checker and original Python
checker validate all 207 conformance cases and 400 mutation controls. An
additional comparison verifies complete certificate equality on 207 cases.
Two complete three-arm runs retain all 756 raw samples on the same fourteen
workloads. The declared eleven-pair phase campaign additionally retains 308
samples for the current producer. Large local planning gains do not remove
extra load or certificate-checking cost; runtime conclusions must use the
complete path, not planner speed alone. A gain appearing in only one repetition
is not a stable end-to-end benefit.

## Same-guarantee ordinary consumer

The complete-cost experiment's ordinary publication carries epochs, copied
frontiers, descriptors and costs but no potentials. `ParseOrdinaryExact`
validates all fields and the native metadata/coverage/lifetime/arithmetic
contract via the existing safety checker. `RecomputedOptimum` independently
evaluates the prefix recurrence by decreasing-start bitmap unions for each
right endpoint, retaining only the scalar minimum for each prefix, not parents
or an optimal plan. It neither calls a producer nor reads its potentials or
last-use frontier. Single-step feasibility gives a finite candidate at every
prefix. Induction on prefixes, with the exact interval-union/lifetime test,
therefore gives the true global minimum under the same admitted finite model.
Acceptance additionally requires the supplied feasible total to equal that
minimum. Every accepted ordinary plan is consequently globally optimal, exactly
the guarantee of the certified consumer; there is no trusted-solver exemption.
Positive page weights imply that an optimum has no noncanonical extra pages.

The scalar consumer uses O(TI+T^2+TP) time and O(T+P) working storage beyond its
normalized input and supplied plan. This standard exact-DP recomputation is a
strong ordinary baseline, not a new optimality theorem. The certified consumer
instead verifies supplied lower bounds by all feasible-interval inequalities.
Both retain common input admission and native safety assumptions. Written
arguments and finite normal/optimized evidence checks do not mechanically prove
either implementation or establish independent novelty.
