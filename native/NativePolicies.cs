// MIT-licensed native policy additions; see ../LICENSE.
// No timers here. allocator.cpp and the mandatory projection are unchanged.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;

namespace P054Native {
public sealed class PolicyReplay {
    public Trace Trace;
    public Plan Plan;
    public Output Actual;
    public int ArenaBytes;
}
public static partial class Bridge {
    public const long FixedVisitPrice = 1; // fixed before execution, never fitted
    public static readonly string[] Policies = {
        "fresh", "longest-feasible", "four-step", "exact-rho0-range-min", "exact-rho1-incremental"
    };

    // Share immutable declarations, requirements and masks; change only accounting.
    public static Trace WithPrice(Trace x, long rho) {
        Need(rho>=0 && rho<=1<<20,"visit price bound");
        return new Trace {Id=x.Id,B=x.B,A=x.A,Heads=x.Heads,Setup=x.Setup,Rho=rho,
            Bound=checked(x.T*(x.Setup+(1+rho*x.T)*x.Pages.Sum(p=>p.Weight))),
            Pages=x.Pages,Frontiers=x.Frontiers,Required=x.Required,Mandatory=x.Mandatory};
    }
    // Exactly Python baseline's anchored cap floor(s/4)*4+3, not s+3.
    static Plan Reuse(Trace x, bool anchoredFour) {
        var es=new List<Epoch>();long total=0;int s=0;
        while(s<x.T) {
            int cap=anchoredFour?Math.Min(x.T-1,(s/4+1)*4-1):x.T-1;
            var seen=new bool[x.Pages.Length];int first=0,last=x.T-1,end=s-1;
            for(int t=s;t<=cap;++t) {
                foreach(int p in x.Required[t]) if(!seen[p]) {
                    seen[p]=true;
                    first=Math.Max(first,x.Pages[p].First);last=Math.Min(last,x.Pages[p].Last);
                }
                if(first>s || last<t)break;
                end=t;
            }
            Need(end>=s,"singleton must be feasible");
            // A failed extension may have inserted pages; materialize the accepted union.
            var u=Union(x,s,end);long cost=Cost(x,u,s,end);
            es.Add(new Epoch {Start=s,End=end,Pages=u,Cost=cost});total=checked(total+cost);s=end+1;
        }
        return new Plan {Epochs=es.ToArray(),Cost=total}; // no optimizer/potentials
    }
    public static Plan LongestFeasible(Trace x) {return Reuse(x,false);}
    public static Plan FourStep(Trace x) {return Reuse(x,true);}

    // Faithful port of src/producer.py RangeMin: range-add, point replacement,
    // and lexicographic (value,start) minima. Finite admitted bounds fit Int64.
    sealed class RangeMin {
        readonly int n;readonly long inf;readonly long[] val,lazy;readonly int[] arg;
        public RangeMin(int count,long infinity) {
            n=count;inf=infinity;val=Enumerable.Repeat(inf,4*n).ToArray();lazy=new long[4*n];arg=new int[4*n];Init(1,0,n-1);
        }
        void Init(int v,int l,int r) {arg[v]=l;if(l<r){int m=(l+r)/2;Init(v*2,l,m);Init(v*2+1,m+1,r);}}
        void Put(int v,long d) {val[v]=checked(val[v]+d);lazy[v]=checked(lazy[v]+d);}
        void Push(int v) {if(lazy[v]!=0){Put(v*2,lazy[v]);Put(v*2+1,lazy[v]);lazy[v]=0;}}
        static (long,int) Best((long,int) a,(long,int) b) {
            return a.Item1<b.Item1 || (a.Item1==b.Item1 && a.Item2<=b.Item2)?a:b;
        }
        void Pull(int v) {var b=Best((val[v*2],arg[v*2]),(val[v*2+1],arg[v*2+1]));val[v]=b.Item1;arg[v]=b.Item2;}
        public void Set(int i,long x) {Set(1,0,n-1,i,x);}
        void Set(int v,int l,int r,int i,long x) {
            if(l==r){val[v]=x;lazy[v]=0;return;}Push(v);int m=(l+r)/2;
            if(i<=m)Set(v*2,l,m,i,x);else Set(v*2+1,m+1,r,i,x);Pull(v);
        }
        public void Add(int a,int b,long d) {if(a<=b)Add(1,0,n-1,a,b,d);}
        void Add(int v,int l,int r,int a,int b,long d) {
            if(b<l || r<a)return;if(a<=l && r<=b){Put(v,d);return;}
            Push(v);int m=(l+r)/2;Add(v*2,l,m,a,b,d);Add(v*2+1,m+1,r,a,b,d);Pull(v);
        }
        public (long,int) Min(int a,int b) {return Min(1,0,n-1,a,b);}
        (long,int) Min(int v,int l,int r,int a,int b) {
            if(b<l || r<a)return (inf,n);if(a<=l && r<=b)return (val[v],arg[v]);
            Push(v);int m=(l+r)/2;return Best(Min(v*2,l,m,a,b),Min(v*2+1,m+1,r,a,b));
        }
    }
    public static Plan ProduceRangeMin(Trace x) {
        Need(x.Rho==0,"range-min kernel requires rho=0");
        long bound=checked(x.T*(x.Setup+x.Pages.Sum(p=>p.Weight))+1);
        var tree=new RangeMin(x.T,checked(4*bound));var last=Enumerable.Repeat(-1,x.Pages.Length).ToArray();
        var expiry=Enumerable.Range(0,x.T).Select(t=>new List<int>()).ToArray();
        for(int p=0;p<x.Pages.Length;++p)if(x.Pages[p].Last+1<x.T)expiry[x.Pages[p].Last+1].Add(p);
        var d=new long[x.T+1];var parent=new int[x.T+1];int lower=0;
        for(int t=0;t<x.T;++t) {
            foreach(int p in expiry[t])lower=Math.Max(lower,last[p]+1);
            foreach(int p in x.Required[t])lower=Math.Max(lower,x.Pages[p].First);
            tree.Set(t,checked(d[t]+x.Setup));
            foreach(int p in x.Required[t]) {tree.Add(last[p]+1,t,x.Pages[p].Weight);last[p]=t;}
            var best=tree.Min(lower,t);Need(best.Item2<=t,"feasible range minimum");d[t+1]=best.Item1;parent[t+1]=best.Item2;
        }
        var es=new List<Epoch>();int end=x.T;
        while(end>0){int s=parent[end];var u=Union(x,s,end-1);es.Add(new Epoch {Start=s,End=end-1,Pages=u,Cost=Cost(x,u,s,end-1)});end=s;}
        es.Reverse();return new Plan {Epochs=es.ToArray(),Potentials=d,Cost=d[x.T]};
    }
    static bool ExactPolicy(string policy) {return policy==Policies[3] || policy==Policies[4];}
    static Plan BuildPolicy(Trace x,string policy) {
        switch(policy) {
            case "fresh":return Fresh(x);
            case "longest-feasible":return LongestFeasible(x);
            case "four-step":return FourStep(x);
            case "exact-rho0-range-min":return ProduceRangeMin(x);
            case "exact-rho1-incremental":return Produce(x);
            default:throw new InvalidDataException("unknown policy");
        }
    }
    // Shared complete decoded-input path for every arm: price/plan/check,
    // mask/index construction, allocate, descriptors, execute, project, guards/free.
    // The driver verifies/serializes after this returns; no arena or plan is reused.
    public static PolicyReplay ReplayPolicy(Trace original,string policy) {
        Need(Policies.Contains(policy),"unknown policy");
        var x=WithPrice(original,policy==Policies[4]?FixedVisitPrice:0);
        var plan=BuildPolicy(x,policy);Check(x,plan,ExactPolicy(policy));
        Output actual;int bytes;
        using(var arena=new Arena(x)){bytes=arena.ArenaBytes;arena.Prepare(plan);actual=arena.Execute(plan);}
        return new PolicyReplay {Trace=x,Plan=plan,Actual=actual,ArenaBytes=bytes};
    }
    // Serialization shape for the existing Python safety checker only. Zero
    // placeholders are not optimality evidence and do not invoke an optimizer.
    static object PolicyCertificate(Trace x,Plan plan,bool optimal) {
        if(optimal)return Certificate(x,plan);
        return Certificate(x,new Plan {Epochs=plan.Epochs,Cost=plan.Cost,Potentials=new long[x.T+1]});
    }
    sealed class PolicyCase {
        public Trace Trace;public string Stratum,Suite;public JsonElement Input;
    }
    static List<PolicyCase> LoadPolicyCases(string root) {
        var all=new List<PolicyCase>();string file=Path.Combine(root,"inputs","traces.jsonl");
        Need(new FileInfo(file).Length<=4*1024*1024,"corpus file bound");
        foreach(string line in File.ReadLines(file))using(var doc=JsonDocument.Parse(line)) {
            var r=doc.RootElement;var input=r.GetProperty("trace");
            all.Add(new PolicyCase {Trace=ParseTrace(input,r.GetProperty("id").GetString()),
                Stratum=r.GetProperty("stratum").GetString(),Suite="retained-200",Input=input.Clone()});
            Need(all.Count<=200,"corpus count");
        }
        Need(all.Count==200 && all.Select(c=>c.Trace.Id).Distinct().Count()==200,"corpus identity");
        foreach(string id in new[]{"native-wide-repeat","native-wide-rotate","native-wide-recycle","native-edge-capzero","native-edge-empty","native-edge-address64","native-edge-maxcost"}) {
            var x=id.StartsWith("native-wide-")?Synthetic(id):Edge(id);
            using(var doc=JsonDocument.Parse(JsonSerializer.Serialize(TraceObject(x))))
                all.Add(new PolicyCase {Trace=x,Stratum=id,Suite="native-controls-7",Input=doc.RootElement.Clone()});
        }
        return all;
    }
    static void SameCertificate(Trace x,Plan a,Plan b) {
        Need(JsonSerializer.Serialize(Certificate(x,a))==JsonSerializer.Serialize(Certificate(x,b)),"full certificate/tie mismatch: "+x.Id);
    }
    // Functional only. Historical Conformance/Measure/ComparePlanners untouched.
    public static void ComparePoliciesFunctional(string root,string output) {
        Directory.CreateDirectory(output);var all=LoadPolicyCases(root);var saved=LoadCertificates(Path.Combine(root,"results","campaign","certificates.jsonl"));
        int controls=RunPolicyTests(),runs=0;
        using(var inputs=new StreamWriter(Path.Combine(output,"cases.jsonl")))
        using(var agreement=new StreamWriter(Path.Combine(output,"planner-agreement.jsonl")))
        using(var rows=new StreamWriter(Path.Combine(output,"policies.jsonl")))foreach(var item in all) {
            var original=item.Trace;var zero=WithPrice(original,0);var priced=WithPrice(original,FixedVisitPrice);
            var declared=Produce(original);Check(original,declared,true);SameCertificate(original,declared,ProduceReference(original));
            if(saved.ContainsKey(original.Id))SameCertificate(original,declared,ParsePlan(original,saved[original.Id]));
            var fast=ProduceRangeMin(zero);Check(zero,fast,true);
            SameCertificate(zero,fast,Produce(zero));SameCertificate(zero,fast,ProduceReference(zero));
            var weighted=Produce(priced);Check(priced,weighted,true);SameCertificate(priced,weighted,ProduceReference(priced));
            inputs.WriteLine(JsonSerializer.Serialize(new {id=original.Id,stratum=item.Stratum,suite=item.Suite,trace=item.Input}));
            agreement.WriteLine(JsonSerializer.Serialize(new {id=original.Id,declared_visit_weight=original.Rho,
                declared_certificate=Certificate(original,declared),rho0_certificate=Certificate(zero,fast),rho1_certificate=Certificate(priced,weighted),
                declared_direct_incremental_equal=true,rho0_three_exact_equal=true,rho1_direct_incremental_equal=true}));
            var expected=Expected(original);
            foreach(string policy in Policies) {
                var replay=ReplayPolicy(original,policy);var x=replay.Trace;var plan=replay.Plan;var actual=replay.Actual;
                Equal(actual.MandatoryValues,expected);
                long publication=0,visits=0,pageVisits=0,loads=0,bytes=0,copies=0;ulong sink=0;
                foreach(var e in plan.Epochs) {
                    long weight=e.Pages.Sum(p=>x.Pages[p].Weight);publication=checked(publication+x.Setup+weight);
                    visits=checked(visits+(e.End-e.Start+1)*weight);pageVisits+=(e.End-e.Start+1)*e.Pages.Length;copies+=e.Pages.Length;
                    for(int t=e.Start;t<=e.End;++t)foreach(int p in e.Pages)for(int lane=0;lane<Cap(x,t,x.Pages[p]);++lane) {
                        ++loads;bytes+=x.Pages[p].Width;sink=unchecked(sink*1099511628211UL+(ulong)Payload(x.Pages[p],lane)+1);
                    }
                }
                Need(plan.Cost==checked(publication+x.Rho*visits),"accounting identity");
                Need(actual.Loads==loads && actual.Bytes==bytes && actual.Publications==plan.Epochs.Length && actual.DescriptorCopies==copies && actual.Sink==sink,"native count/sink mismatch");
                rows.WriteLine(JsonSerializer.Serialize(new {id=x.Id,stratum=item.Stratum,suite=item.Suite,policy,planning_visit_weight=x.Rho,
                    checker=ExactPolicy(policy)?"optimality":"safety-only",certificate=PolicyCertificate(x,plan,ExactPolicy(policy)),
                    publication_cost=publication,weighted_page_visits=visits,page_visits=pageVisits,
                    cost_at_fixed_visit_price=checked(publication+FixedVisitPrice*visits),rho0_optimum=fast.Cost,rho1_optimum=weighted.Cost,
                    actual_values=actual.MandatoryValues,actual_loads=actual.Loads,actual_bytes=actual.Bytes,
                    publications=actual.Publications,descriptor_copies=actual.DescriptorCopies,sink=actual.Sink,arena_bytes=replay.ArenaBytes,passed=true}));
                ++runs;
            }
        }
        File.WriteAllText(Path.Combine(output,"functional-summary.json"),JsonSerializer.Serialize(new {status="FUNCTIONAL_PASSED",retained_cases=200,native_controls=7,
            native_policy_replays=runs,policies=Policies,fixed_visit_price=FixedVisitPrice,declared_direct_incremental_fullcert_cases=207,
            repriced_rho0_three_exact_fullcert_cases=207,repriced_rho1_direct_incremental_fullcert_cases=207,
            saved_fullcert_cases=200,targeted_controls=controls,performance_measurements_started=false}));
    }
}
}
