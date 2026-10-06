# Mathematical arguments

These are written mathematical proofs, not proof-assistant certificates. The executable checks cover finite cases only. They assume the well-formed trace and abstract launch semantics in `docs/model.md`; in particular, inputs state truthful lifetime and mask facts for the modeled execution. The producer is untrusted. The correctness of a particular implementation of the checker is not established merely by its name.

Let time be 0,...,T-1. Incarnation p has closed life [a_p,b_p] and positive integral weight w_p. R_t is a finite set of required live incarnations. Let lambda>=0 be the setup charge. Write U(s,t)=union_{q=s}^t R_q and W(s,t)=sum_{p in U(s,t)} w_p. Feasible intervals have a_p<=s<=t<=b_p for all p in U(s,t). All cost and optimality statements below are for this fixed finite input, not unknown future queries.

## M1. The spatial image lemma

For any finite directed dependency graph with conjunctive reachable read atoms and a fixed logical-to-incarnation mapping, the image R of the reachable atoms is the unique least set covering all dependencies. With positive incarnation costs it is also the unique least-cost covering set.

Proof. Each reachable atom names a fixed incarnation, so every covering set must include that incarnation. Hence every covering set contains R. Conversely, including R provides the page of every reachable atom, so R covers all dependencies. For a strictly larger set S, the sum over S exceeds the sum over R because all extra weights are positive. Directed cycles only affect how reachability is computed, not either implication. This proves the claim for arbitrary graphs without an interval or laminar restriction. No graph-induced set-cover hardness follows from this model; interchangeable OR choices would be a different semantics. QED.

## M2. Abstract launch safety and canonical epochs

A constant selected list S satisfies the declared descriptor-validity and dependency-coverage contract on [s,t] if and only if it covers U(s,t) and every selected incarnation lives throughout [s,t], provided descriptors, bindings, lane initialization, address bounds and declared masks satisfy the model's well-formedness conditions. This contract implies abstract launch safety. The canonical union U is the unique least-cost contract-valid list whenever any such list exists, for both rho=0 and rho>=0. Whole-epoch liveness is a declared descriptor requirement, not a necessary condition for every possible masked-load implementation: a fully masked inactive descriptor might issue no load in a different semantics.

Proof. Necessity of coverage follows from M1 at every step. A selected incarnation is consulted as an epoch descriptor at each step and, under this lifetime-based contract, must be live for the whole interval; because its life is contiguous, endpoint containment is necessary and sufficient. For sufficiency, consider any abstract load (p,i) at a step q. The descriptor names the same immutable incarnation as the metadata. Lifetime containment makes p live at q. The launch requires 0<=i<cap_q(p)<=length_p, so the lane is initialized and its token coordinate base_p+i is <=frontier_q. The byte interval begins at slot_p*2*page_size + i*width_p and ends no later than the checked exclusive allocation end. Slot stride is at least each allocation's extent, so distinct slots do not overlap; a reused slot cannot have two live incarnations by well-formedness. Thus this abstract load has the required address, generation, initialization and causal properties. Every required atom has p in U subset S and upper endpoint at most cap_q(p), so all its lanes occur in the abstract read set. The argument holds for every step; completed-before-next sequencing excludes a reclamation transition during these loads.

Projecting S to U preserves both properties. Its epoch cost is lambda+(1+rho*(t-s+1))*sum w_p. The coefficient of every w_p is positive, so deleting any page outside U strictly decreases the cost. Therefore an optimal valid partition must be canonical epoch by epoch. This does not prove that a native kernel realizes the specified read set or that the attention result matches a dense computation. QED.

## F1. Exact lifetime frontier

Let last_p(q) be the last occurrence of p among R_0,...,R_q, or -1 if there is none. Set L_-1=0. At time t define

```
L_t = max(L_{t-1}, max_{p in R_t} a_p,
          max_{p: b_p=t-1} (last_p(t-1)+1)),
```

where the maximum of an empty family contributes zero. The feasible starts of intervals ending at t are exactly L_t,...,t.

Proof. Equivalently define H_t as the maximum of (i) zero, (ii) a_p for every p occurring at least once by t, and (iii) last_p(t)+1 for every page expired strictly before t. We first show that [s,t] is feasible exactly when s>=H_t. If s is feasible and p has occurred by t, then a_p>s would imply an occurrence j>=a_p>s, since every requirement is live. That occurrence belongs to [s,t], contradicting feasibility. Thus all birth terms are <=s, even for pages whose last occurrence precedes s. If p is expired before t, any occurrence at or after s would similarly contradict feasibility, so last_p(t)<s and its expiry term is <=s.

Conversely, suppose s>=H_t and p occurs in [s,t]. Its birth term is included in H_t, so a_p<=s. If b_p<t, its last occurrence by t is at least s, making the expiry term greater than s, a contradiction. Hence b_p>=t. All pages in U(s,t) satisfy both endpoints, so the interval is feasible.

The recurrence maintains H_t. Previously seen birth terms persist, and new required pages add their births. At t an expiry term is first introduced exactly for b_p=t-1. A well-formed page has no occurrence after expiry, so its recorded last occurrence never changes after introduction. The other terms persist in the running maximum. Therefore L_t=H_t by induction. Finally, every page in R_t is live at t, so [t,t] is feasible and L_t<=t. An unused expired page has last=-1 and contributes zero; it must not spuriously force a cut. QED.

## P1. Prefix recurrence and range-add invariant

Let D[0]=0, and let D[t+1] be the least publication cost of a valid partition of steps 0,...,t. Then

```
D[t+1] = min_{L_t <= s <= t} (D[s] + lambda + W(s,t)).
```

The range-update kernel for this recurrence takes O((T+I+P) log T) time after input normalization, where I=sum_t |R_t| and P is the incarnation count. The supplied producer additionally sorts each requirement set, costing O(I log P), and constructs sorted canonical output in O(I+K log P) time for K emitted descriptors. These deterministic-ordering and output costs are not absorbed into the range-update bound. Working storage beyond normalized input and emitted descriptors is O(T+P).

Proof. Every valid partition has a final interval [s,t]. M2 lets us use its canonical union; F1 supplies exactly its feasible starts. Its preceding epochs cost at least D[s]. Conversely, a minimizing prefix partition followed by any feasible [s,t] is a valid partition and realizes the stated value. This proves the recurrence, existence of minimizing parents, and global optimality of their backtracking path by induction.

For the fast implementation, maintain one tree leaf for every start s inserted so far. Just before the step-t minimum query, its value is D[s]+lambda+W(s,t). Insert the new leaf t with D[t]+lambda. For each p in R_t, let j be its previous occurrence, initially -1. A start s already has p in U(s,t-1) exactly when s<=j. Thus p is newly added to its union exactly for j<s<=t, a single contiguous range. Adding w_p to that range and setting last_p=t preserves the invariant. The order of distinct p within R_t is immaterial. By F1 the minimum is queried only over [L_t,t]. No future leaf participates.

A standard lazy range tree realizes each update, point replacement and range query in O(log T) time. There are T replacements, I weight additions, and T queries. Processing birth terms takes O(I); bucketing and processing expiries takes O(T+P), with each page expiring once. The DP values, parents, tree, occurrence indices and expiry buckets use O(T+P) memory. Backtracking uses O(T) time; materializing canonical descriptors adds output/union construction work and is not hidden inside a claim that output has constant size. This is an application of a conventional data structure, not a new range-tree theorem. QED.

## C1. Soundness and completeness of optimality evidence

For rho>=0, suppose the checker validates an epoch partition with canonical lists and exact costs, and nonnegative integers d[0],...,d[T] satisfying d[0]=0 and

```
d[t+1] <= d[s] + c_rho(s,t)
```

for every feasible interval. If the selected partition has total cost d[T], its cost is globally minimum among all valid page lists and contiguous partitions of this fixed trace. Conversely every optimal valid partition admits such evidence.

Proof (soundness). Let any alternative valid partition have endpoints 0=u_0<u_1<...<u_k=T. Applying the displayed inequality to each interval [u_i,u_{i+1}-1] gives d[u_{i+1}]-d[u_i] <= c_rho(u_i,u_{i+1}-1). Summing cancels every interior potential, leaving d[T] <= the alternative's canonical cost. By M2, any noncanonical alternative costs at least its canonical projection. The checked selected partition realizes d[T], establishing equality with the global optimum. M2 also supplies its abstract dependency and safety properties. No claim about the producer's own code or claimed algorithm was used.

Proof (completeness). Finite single-step partitions exist, so choose an optimal partition and let d[v] be the true optimum for prefix [0,v-1], with d[0]=0. Concatenating an optimal prefix at s with a feasible interval [s,t] proves d[t+1] <= d[s]+c_rho(s,t). Potentials are nonnegative integers. Each prefix has a fresh canonical plan bounded by T*(lambda+(1+rho*T)*sum_p w_p), so the executable bound admits every d[v]. Positive weights make the chosen optimal partition canonical by M2. All descriptor metadata and frontier copies can be taken from the well-formed input, and exact arithmetic gives the equality at T. Hence the checker accepts this certificate. This is existence of a certificate, not a uniqueness or field-minimality theorem. QED.

## C2. Checker cost and evidence size

The checker does not use F1 or the range tree. For each right endpoint t, it scans starts backwards, incrementally unions the requirements, and maintains the maximum birth and minimum death of that union. It checks each of the T(T+1)/2 intervals directly. The interval loop takes O(T^2+TI) time: each R_s is traversed at most T-s times, and each interval adds constant other work. If G counts dependency structure including root entries, B the number of bindings, and K the number of emitted descriptors, total time in the supplied implementation is O(G log G+B+P log P+T^2+TI+K). The G log G term conservatively includes sorting reachable node indices; the lifetime grouping/sorting accounts for P log P. Normalized requirements occupy O(I) storage. The certificate carries T+1 potentials, T copied query frontiers, at most T epochs and K descriptors: O(T+K) bounded-size words. It does not carry a quadratic table of all interval costs, but it is not an O(T)-byte object independent of selected lists.

These complexity bounds are for the algorithms over finite sets and exact integers. They are not measured GPU latency or a machine-checked complexity proof of the Python runtime.

## G1. Maximal reuse has a tight factor-two publication bound

Define maximal reuse by repeatedly taking the longest feasible interval from the next unprocessed step. It knows the entire trace when constructing each constant union. At rho=0, let C_G be its cost, OPT the optimal cost, and k_* the number of epochs of any chosen optimal partition. Then

```
C_G <= 2*OPT - lambda*k_* <= 2*OPT.
```

The factor two is approached by a family with two page incarnations and three steps in the abstract positive-integer-weight model without a fixed upper weight cap. The inequality also holds for every admitted executable trace, but the limiting family M->infinity is not wholly admitted by the reader's weight cap of 2^20. Its retained finite cases have ratios strictly below two. There is no analogous bound asserted here for rho>0.

Proof. Feasibility is hereditary under taking contiguous subintervals, since a smaller union and a shorter lifetime interval preserve containment. The standard endpoint domination argument implies that maximal reuse uses no more epochs than any valid partition: induct on the epoch index, comparing endpoints. If a greedy start is beyond the comparator's current endpoint, domination is automatic. Otherwise, the suffix from that greedy start to the comparator's endpoint is a subinterval of the comparator's epoch and hence feasible; maximality extends at least that far. Thus k_G<=k_*.

An epoch of the optimal partition intersects at most two greedy epochs. Otherwise it contains a complete middle greedy epoch and the first step of the next greedy epoch. Their union is a contiguous subinterval of a feasible optimal epoch, contradicting the middle greedy epoch's maximality. Now charge each greedy page inclusion (G,p) to an occurrence of p inside G, and hence to the optimal epoch O containing that occurrence. For a fixed (O,p), at most two greedy epochs meet O, so at most two charges are possible. The charged weight is w_p. Summing shows that the greedy page-weight total W_G is at most twice W_* of the optimal partition. Therefore C_G=lambda*k_G+W_G <= lambda*k_*+2*W_* =2*OPT-lambda*k_*.

For tightness, take lives a:[0,1] with weight 1 and b:[0,2] with weight M>0, requirements R_0={a}, R_1=R_2={b}, and lambda=1. Maximal reuse chooses [0,1],[2,2], costing 2M+3. The partition [0,0],[1,2] costs M+3. Of the other partitions, the one-span partition violates a's expiry, and the all-singleton partition costs 2M+4, no less than M+3 for M>=1. Thus OPT=M+3 for integral M>=1 and (2M+3)/(M+3) approaches two. The two life intervals are laminar, so laminar lifetimes do not make greedy weighted reuse exact. Both algorithms here are offline, not online policies. QED.

## G2. Births invalidate a tempting counterexample

Add a third page c of weight 1, born at step 2 and needed at step 2, to the preceding example. Its life is [2,2]. The proposed improvement [1,2] would include c at step 1, violating its birth. With lambda=1 and M=1024, both the optimum and maximal reuse cost 2052, whereas the all-singleton plan costs 2053. This four-partition calculation is retained as a negative control. It illustrates why a smaller sum of repeated weights is not sufficient evidence of an admissible optimization.

## S1. Visit-price monotonicity

For a partition A, let C_0(A) be publication cost and V(A)=sum_epochs length(epoch)*sum_{p in U(epoch)} w_p its weighted visits. For rho_2>rho_1>=0 and any respective optimal partitions A_1,A_2, V(A_2)<=V(A_1) and C_0(A_2)>=C_0(A_1).

Proof. Optimality gives C_0(A_1)+rho_1 V(A_1)<=C_0(A_2)+rho_1 V(A_2) and C_0(A_2)+rho_2 V(A_2)<=C_0(A_1)+rho_2 V(A_1). Adding gives (rho_2-rho_1)(V(A_2)-V(A_1))<=0, hence the first conclusion. Substituting it into the first inequality gives C_0(A_2)-C_0(A_1)>=rho_1(V(A_1)-V(A_2))>=0. This is a general elementary parametric-optimization fact, not a new attention theorem. The corpus's unweighted page-visit counter must not be substituted for V when weights differ. QED.

## X1. An equivalent cut formulation

This characterization concerns rho=0 and does not change the implemented optimization objective. Let X be the set of cuts after steps 0,...,T-2. For every used incarnation p, let f_p and l_p be its first and last required occurrences. A partition using canonical lists is feasible exactly when X meets [a_p-1,f_p-1] for every used p with a_p>0 and X meets [l_p,b_p] for every used p with b_p<T-1. All these are intervals of cut positions. For a page whose ordered occurrences are t_1<...<t_m, its number of descriptor publications equals

```
1 + sum_{j=1}^{m-1} indicator(X intersects [t_j,t_{j+1}-1]).
```

Consequently the partition cost is

```
lambda + sum_{p used} w_p + lambda*|X|
+ sum_{p used} w_p * sum_consecutive_occurrences indicator(X hits their gap).
```

Proof. The epoch containing the first occurrence of p starts at least at a_p exactly when there is a cut after some step in [a_p-1,f_p-1]; if a_p=0 no birth cut is required. Every later p-containing epoch starts no earlier, so this single condition suffices for all its occurrences. Symmetrically, the epoch containing its last occurrence ends no later than b_p exactly when a cut meets [l_p,b_p], unless b_p=T-1. Earlier p-containing epochs end no later. These two endpoint tests for every used page are exactly epoch lifetime containment, proving feasibility.

Successive occurrences of a page belong to different epochs exactly when a cut lies between them. The sequence of epoch indices of a page's occurrences is nondecreasing. Its number of distinct occupied epochs is one plus the number of changes between adjacent occurrences, even if a gap contains several empty-of-p epochs. Therefore the displayed count is exact: several cuts in one occurrence gap charge the page only once. Summing its weighted count over used pages and adding lambda per epoch, with |X|+1 epochs, proves the cost identity. QED.

Corollary. If all used pages live throughout the complete trace, the one-span canonical plan is feasible and has minimum publication cost: the cut representation has no mandatory lifetime intervals and every cut contribution is nonnegative. It need not be the unique optimum when setup is zero. Thus varying page lifetimes, not static graph topology, are what make the rho=0 problem nontrivial. A general birth/expiry instance cannot be justified using this special case.

## I1. Metadata does not imply attention accuracy

Consider real-valued attention extending the metadata language. At one causal step, declare only the first of two eligible pages required and select it. Give its value zero and the omitted page value M>0. If the omitted page's logit exceeds the selected page's logit by delta, the dense output is M*exp(delta)/(1+exp(delta)), while the selected output is zero. Thus the error approaches M as delta increases. Without a supplied bound on values, letting M grow rules out a finite uniform error guarantee from these metadata obligations alone. This unbounded claim concerns the real-valued extension, not representable fp16 or int8 values. A fixed numerical range can impose a trivial range bound, but the page certificate does not establish a small approximation error within that range. The lane formats in the trace specify storage widths; this artifact implements no numerical attention semantics. This is a mathematical separation argument, not an executed attention or model experiment.

## I2. A fixed-trace optimum is not a future-query guarantee

Suppose a procedure freezes a proper subset S of currently live, causally eligible pages while the dependency specification leaves future requirements unrestricted. Choose an omitted live eligible page p and a next requirement R={p}; keep p live for that next step. This continuation is indistinguishable from one requiring only S before the list is frozen, yet invalidates coverage. Thus a prefix-only observer cannot infer arbitrary future coverage from the current list alone. It must use an authoritative future contract, select the complete eligible universe, or refresh/revalidate as new obligations arrive. The offline optimality theorem assumes the first alternative as a declared complete finite trace and makes no causal-online claim.
