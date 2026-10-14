// Original MIT-licensed code; see ../LICENSE. Owned sequential CPU experiment.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;

namespace P054Native {
public static partial class Bridge {
    static readonly string[] CostArms={"ordinary-exact","certified-incremental","certified-range-min","certified-direct-union"};
    const int CostRounds=8;
    [DllImport("kernel32.dll")] static extern IntPtr GetCurrentProcess();
    [DllImport("kernel32.dll",SetLastError=true)] static extern bool GetProcessTimes(IntPtr h,out long creation,out long exit,out long kernel,out long user);
    static long ProcessCpu() {
        long c,e,k,u;Need(GetProcessTimes(GetCurrentProcess(),out c,out e,out k,out u),"GetProcessTimes failed");return checked(k+u);
    }
    sealed class CostClock {
        public long wall_ticks,process_cpu_100ns;
        public static CostClock Run(Action action) {
            long cpu=ProcessCpu(),wall=Stopwatch.GetTimestamp();
            try{action();}finally{wall=Stopwatch.GetTimestamp()-wall;cpu=ProcessCpu()-cpu;}
            return new CostClock {wall_ticks=wall,process_cpu_100ns=cpu};
        }
    }
    // Independent consumer recurrence: scalar minimum only, no producer call,
    // parents, last-use frontier, segment tree, or transmitted lower bounds.
    static long RecomputedOptimum(Trace x) {
        var d=new long[x.T+1];
        for(int t=0;t<x.T;++t) {
            long best=long.MaxValue,weight=0;int birth=0,death=x.T-1;var seen=new bool[x.Pages.Length];
            for(int s=t;s>=0;--s) {
                foreach(int p in x.Required[s])if(!seen[p]){seen[p]=true;var m=x.Pages[p];weight+=m.Weight;birth=Math.Max(birth,m.First);death=Math.Min(death,m.Last);}
                if(birth<=s && t<=death)best=Math.Min(best,checked(d[s]+x.Setup+(1+x.Rho*(t-s+1))*weight));
            }
            Need(best!=long.MaxValue,"no feasible partition");d[t+1]=best;
        }
        return d[x.T];
    }
    static object OrdinaryPublication(Trace x,Plan p) {
        return new {epochs=p.Epochs.Select(e=>new {start=e.Start,end=e.End,cost=e.Cost,
            pages=e.Pages.Select(i=>new object[]{i,x.Pages[i].Slot,x.Pages[i].Generation,x.Pages[i].Content,x.Pages[i].Width==2?"fp16":"int8",x.Pages[i].Group}).ToArray()}).ToArray(),
            frontiers=x.Frontiers,total_cost=p.Cost};
    }
    public static Plan ParseOrdinaryExact(Trace x,JsonElement c) {
        Exact(c,"epochs","frontiers","total_cost");
        var fs=Array(c.GetProperty("frontiers"),x.T,x.T);
        for(int t=0;t<x.T;++t)Need(N(fs[t],0,int.MaxValue)==x.Frontiers[t],"ordinary frontier mismatch");
        var plan=new Plan {Cost=Number(c.GetProperty("total_cost"),0,x.Bound)};
        var es=Array(c.GetProperty("epochs"),x.T,1);plan.Epochs=new Epoch[es.Length];
        for(int j=0;j<es.Length;++j) {
            var e=es[j];Exact(e,"start","end","pages","cost");int s=N(e.GetProperty("start"),0,x.T-1),t=N(e.GetProperty("end"),s,x.T-1);
            var selected=new List<int>();int prior=-1;
            foreach(var desc in Array(e.GetProperty("pages"),x.Pages.Length)) {
                var v=Array(desc,6,6);int p=N(v[0],0,x.Pages.Length-1);Need(p>prior,"ordinary descriptor order");prior=p;var m=x.Pages[p];
                Need(N(v[1],0,int.MaxValue)==m.Slot && N(v[2],0,int.MaxValue)==m.Generation && N(v[3],0,int.MaxValue)==m.Content && Width(v[4])==m.Width && N(v[5],0,int.MaxValue)==m.Group,"ordinary descriptor mismatch");selected.Add(p);
            }
            plan.Epochs[j]=new Epoch {Start=s,End=t,Pages=selected.ToArray(),Cost=Number(e.GetProperty("cost"),0,x.Bound)};
        }
        Check(x,plan,false);Need(plan.Cost==RecomputedOptimum(x),"ordinary recomputed optimum mismatch");return plan;
    }
    public static object CompleteCostProtocol() {
        return new {protocol="same-contract-complete-cost",inputs=207,retained=200,controls=7,arms=CostArms,rounds=CostRounds,
            calls_per_arm_round=1,measured_calls=207*4*CostRounds,warmup_calls=207*4,
            order="case in frozen order; arm[(round+position)%4], 8 rounds, two full position cycles; one untimed full call per arm per case",
            objective="rho=0; global optimality and identical descriptor/lifetime/coverage/native contract",
            ordinary_consumer="no transmitted potentials; parse plan, safety/cost check, independent backward-bitmap scalar optimum recomputation",
            certified_consumer="full potentials; ParsePlan and all feasible-interval inequalities",
            phases=new[]{"acquisition","planning","serialization","publication","consumer","native","cleanup"},
            full_timer="one actual invocation enclosing all seven phases and nested clock/accounting overhead; NOT sum of phase medians",
            acquisition="File.ReadAllBytes, close, JSON decode and ParseTrace for every call; same prewritten local UTF-8 file, OS cache uncontrolled",
            publication="File.WriteAllBytes with close; consumer File.ReadAllBytes with close; no explicit durable flush, network or serving",
            native="fresh masks/index, C++ allocation, descriptor materialization, nb_run, mandatory projection, guards and free",
            excluded="initial input-file preparation; build/startup/load; output/reference comparison; raw-record JSON/compression",
            clocks="Stopwatch wall ticks; Win32 GetProcessTimes kernel+user process CPU in 100ns units, coarse quantization; includes background runtime threads",
            zero_policy="retain exact zeros; ratio null when denominator zero; no epsilon, trimming, negative removal, resampling, forced GC or automatic repeats",
            limitations="owned synthetic sequential CPU buffers; no physical disk, RSS, network, GPU, service deployment or latency guarantee"};
    }
    public static void CompleteCostConsumerRegressions(string inputFolder) {
        var first=File.ReadAllLines(Path.Combine(inputFolder,"index.jsonl"))[0];using(var item=JsonDocument.Parse(first)) {
            string id=item.RootElement.GetProperty("id").GetString();using(var doc=JsonDocument.Parse(File.ReadAllBytes(Path.Combine(inputFolder,id+".json")))) {
                var x=ParseTrace(doc.RootElement,id);var exact=Produce(x);
                using(var p=JsonDocument.Parse(JsonSerializer.SerializeToUtf8Bytes(OrdinaryPublication(x,exact))))ParseOrdinaryExact(x,p.RootElement);
                var bad=System.Text.Json.Nodes.JsonNode.Parse(JsonSerializer.Serialize(OrdinaryPublication(x,Fresh(x))));
                Need(Fresh(x).Cost>exact.Cost,"regression parent must be strictly suboptimal");
                foreach(string mutation in new[]{"safe-suboptimal","boolean-total","wrong-generation","unknown-potential"}) {
                    var n=System.Text.Json.Nodes.JsonNode.Parse(JsonSerializer.Serialize(OrdinaryPublication(x,mutation=="safe-suboptimal"?Fresh(x):exact)));
                    if(mutation=="boolean-total")n["total_cost"]=true;
                    if(mutation=="wrong-generation")n["epochs"][0]["pages"][0][2]=0;
                    if(mutation=="unknown-potential")n["potentials"]=new System.Text.Json.Nodes.JsonArray(0);
                    bool rejected=false;try{using(var p=JsonDocument.Parse(n.ToJsonString()))ParseOrdinaryExact(x,p.RootElement);}catch(InvalidDataException){rejected=true;}
                    Need(rejected,"ordinary regression accepted: "+mutation);
                }
            }
        }
    }
    static void CompleteCostCall(string inputFolder,string publication,string id,string arm,int round,int position,StreamWriter raw) {
        var phases=new Dictionary<string,CostClock>();Trace x=null;Plan proposal=null,consumed=null;byte[] input=null,published=null;Output actual=null;int arenaBytes=0;
        var total=CostClock.Run(()=>{
            phases["acquisition"]=CostClock.Run(()=>{input=File.ReadAllBytes(Path.Combine(inputFolder,id+".json"));using(var d=JsonDocument.Parse(input))x=ParseTrace(d.RootElement,id);Need(x.Rho==0,"fixed rho=0");});
            phases["planning"]=CostClock.Run(()=>{proposal=arm=="certified-range-min"?ProduceRangeMin(x):arm=="certified-direct-union"?ProduceReference(x):Produce(x);});
            phases["serialization"]=CostClock.Run(()=>{published=JsonSerializer.SerializeToUtf8Bytes(arm=="ordinary-exact"?OrdinaryPublication(x,proposal):Certificate(x,proposal));});
            phases["publication"]=CostClock.Run(()=>File.WriteAllBytes(publication,published));
            phases["consumer"]=CostClock.Run(()=>{byte[] read=File.ReadAllBytes(publication);using(var d=JsonDocument.Parse(read))consumed=arm=="ordinary-exact"?ParseOrdinaryExact(x,d.RootElement):ParsePlan(x,d.RootElement);});
            phases["native"]=CostClock.Run(()=>{using(var a=new Arena(x)){arenaBytes=a.ArenaBytes;a.Prepare(consumed);actual=a.Execute(consumed);a.Guards();}});
            phases["cleanup"]=CostClock.Run(()=>File.Delete(publication));
        });
        // Full functional comparisons are outside timers. Nothing cached from
        // these checks is used by another measured producer or consumer.
        Equal(actual.MandatoryValues,Expected(x));Check(x,proposal,true);
        Need(JsonSerializer.Serialize(OrdinaryPublication(x,proposal))==JsonSerializer.Serialize(OrdinaryPublication(x,consumed)),"consumed plan correspondence");
        if(raw!=null)raw.WriteLine(JsonSerializer.Serialize(new {id,arm,round,position,objective="rho0-publication",checker="optimality",frequency=Stopwatch.Frequency,
            full=new {total.wall_ticks,total.process_cpu_100ns},phases=phases.ToDictionary(k=>k.Key,k=>(object)new {k.Value.wall_ticks,k.Value.process_cpu_100ns}),
            input_bytes=input.Length,published_bytes=published.Length,published_utf8=Encoding.UTF8.GetString(published),
            actual_values=actual.MandatoryValues,actual_loads=actual.Loads,actual_bytes=actual.Bytes,publications=actual.Publications,
            descriptor_copies=actual.DescriptorCopies,sink=actual.Sink,arena_bytes=arenaBytes,passed=true}));
    }
    public static void MeasureCompleteCost(string inputFolder,string output) {
        CompleteCostConsumerRegressions(inputFolder);var ids=File.ReadAllLines(Path.Combine(inputFolder,"index.jsonl")).Select(s=>{using(var d=JsonDocument.Parse(s))return d.RootElement.GetProperty("id").GetString();}).ToArray();
        Need(ids.Length==207 && ids.Distinct().Count()==207,"frozen complete input identity");string publication=Path.Combine(output,"publication.json");
        int count=0;using(var raw=TimingGzipWriter(Path.Combine(output,"samples.jsonl.gz")))foreach(string id in ids) {
            foreach(string arm in CostArms)CompleteCostCall(inputFolder,publication,id,arm,-1,-1,null);
            for(int r=0;r<CostRounds;++r)for(int p=0;p<4;++p){CompleteCostCall(inputFolder,publication,id,CostArms[(r+p)%4],r,p,raw);++count;}raw.Flush();
        }
        Need(count==6624,"complete measured call count");File.WriteAllText(Path.Combine(output,"completion.json"),JsonSerializer.Serialize(new {status="MEASURED",measured_calls=count,warmup_native_calls=828,consumer_regressions=4}));
    }
}
}
