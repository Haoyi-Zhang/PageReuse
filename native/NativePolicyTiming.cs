// MIT; see ../LICENSE. New current-source comparison, not historical timings.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Text;
using System.Text.Json;

namespace P054Native {
public static partial class Bridge {
    const int PolicyWarmups=3,PolicyRounds=11,PolicyCalls=4;
    public static void ValidatePolicyTimingProtocol() {
        Need(Panel.SequenceEqual(new[]{"case-000","case-001","case-003","case-004","case-005","case-056","case-120","case-160","case-184","case-196","case-199","native-wide-repeat","native-wide-rotate","native-wide-recycle"}),"fixed timing panel changed");
        Need(Policies.SequenceEqual(new[]{"fresh","longest-feasible","four-step","exact-rho0-range-min","exact-rho1-incremental"}) && FixedVisitPrice==1,"fixed timing policies/price changed");
    }
    public static object PolicyTimingProtocol() {
        ValidatePolicyTimingProtocol();
        return new {panel=Panel,policies=Policies,warmup_complete_calls_per_arm=PolicyWarmups,rounds=PolicyRounds,calls_per_arm_per_round=PolicyCalls,
            expected_clock_samples=14*5*PolicyRounds*PolicyCalls,fixed_visit_price=FixedVisitPrice,
            order="for each case: policy[(round+position)%5]; 11 rounds = two cycles plus one rotation, not perfectly position-balanced",
            warmup_order="policy[(warmup+position)%5]; exactly three untimed complete calls per arm",
            phases=new[]{"price preparation + native planner (including full plan materialization)","appropriate managed safety/optimality checker on that plan","actual shared ReplayPolicy complete decoded-input path"},
            complete_includes="price/plan/check/mask/index/allocate/descriptors/native execute/mandatory projection/guards/free",
            excluded="compile, input/reference decoding, source/binary checks, output comparison, compression and JSON IO",
            guarantees="three heuristics are safety-checked only; rho0 and rho1 exact arms also certify their different declared accounting objectives",
            raw_values="not repeated: every timed execution is compared outside timers with the complete functional vector, and its full certificate/counts/sink",
            retention="all four individual calls, zero ticks and slowdowns; no outlier filter, chosen seed, fitted price, automatic repeats or forced GC",
            interpretation="synthetic sequential CPU buffer; not GPU attention, deployment or a serving-population estimate"};
    }
    static string[] TimingLines(string path) {
        // Cap bytes actually decompressed, not the compressed input length.
        using(var file=File.OpenRead(path))using(var decoded=path.EndsWith(".gz",StringComparison.Ordinal)?(Stream)new GZipStream(file,CompressionMode.Decompress):file)
        using(var memory=new MemoryStream()) {
            var buffer=new byte[65536];long total=0;int n;
            while((n=decoded.Read(buffer,0,buffer.Length))!=0){total+=n;Need(total<=256L*1024*1024,"decompressed timing-input bound");memory.Write(buffer,0,n);}
            return Encoding.UTF8.GetString(memory.ToArray()).TrimStart('\uFEFF').Split('\n').Where(s=>s.Trim().Length!=0).ToArray();
        }
    }
    static StreamWriter TimingGzipWriter(string path) {
        return new StreamWriter(new GZipStream(File.Open(path,FileMode.CreateNew),CompressionLevel.Optimal),new UTF8Encoding(false));
    }
    // Prepare only: no Arena, native execution, warmups or clock-counter reads.
    public static void PreparePolicyTimingInputs(string root,string functional,string privateOutput) {
        ValidatePolicyTimingProtocol();var all=LoadPolicyCases(root);
        using(var panel=TimingGzipWriter(Path.Combine(privateOutput,"panel.jsonl.gz")))foreach(string id in Panel) {
            var item=all.Single(c=>c.Trace.Id==id);panel.WriteLine(JsonSerializer.Serialize(new {id,trace=item.Input}));
        }
        int count=0;var seen=new HashSet<string>();
        using(var references=TimingGzipWriter(Path.Combine(privateOutput,"functional-values.jsonl.gz")))
            foreach(string line in TimingLines(Path.Combine(functional,"policies.jsonl.gz")))using(var doc=JsonDocument.Parse(line)) {
                var r=doc.RootElement;string id=r.GetProperty("id").GetString(),policy=r.GetProperty("policy").GetString();
                if(!Panel.Contains(id))continue;Need(Policies.Contains(policy) && seen.Add(id+"/"+policy),"functional panel reference identity");
                references.WriteLine(line.TrimEnd('\r'));++count;
            }
        Need(count==70,"complete 14 by 5 functional references");
    }
    sealed class TimingReference {
        public int[][] Values;public string Certificate;public long Loads,Bytes,Publications,Copies;public ulong Sink;public int ArenaBytes;
    }
    static Dictionary<string,TimingReference> TimingReferences(string file) {
        var refs=new Dictionary<string,TimingReference>();
        foreach(string line in TimingLines(file))using(var doc=JsonDocument.Parse(line)) {
            var r=doc.RootElement;string key=r.GetProperty("id").GetString()+"/"+r.GetProperty("policy").GetString();
            refs.Add(key,new TimingReference {Values=r.GetProperty("actual_values").EnumerateArray().Select(t=>t.EnumerateArray().Select(v=>v.GetInt32()).ToArray()).ToArray(),
                Certificate=r.GetProperty("certificate").GetRawText(),Loads=r.GetProperty("actual_loads").GetInt64(),Bytes=r.GetProperty("actual_bytes").GetInt64(),
                Publications=r.GetProperty("publications").GetInt64(),Copies=r.GetProperty("descriptor_copies").GetInt64(),Sink=r.GetProperty("sink").GetUInt64(),ArenaBytes=r.GetProperty("arena_bytes").GetInt32()});
        }
        Need(refs.Count==70,"timing reference count");return refs;
    }
    static void ValidateTimedReplay(PolicyReplay replay,TimingReference reference,string policy) {
        Equal(replay.Actual.MandatoryValues,reference.Values);
        Need(replay.Actual.Loads==reference.Loads && replay.Actual.Bytes==reference.Bytes && replay.Actual.Publications==reference.Publications &&
            replay.Actual.DescriptorCopies==reference.Copies && replay.Actual.Sink==reference.Sink && replay.ArenaBytes==reference.ArenaBytes,"timed native counts/sink changed");
        Need(JsonSerializer.Serialize(PolicyCertificate(replay.Trace,replay.Plan,ExactPolicy(policy)))==reference.Certificate,"timed full certificate/tie changed");
    }
    // Never called by Prepare or CI. Only the reserved-slot Measure branch.
    public static void MeasurePolicyTiming(string inputFolder,string output,string slotId,Action markStarted) {
        Need(!string.IsNullOrWhiteSpace(slotId) && markStarted!=null,"explicit reserved slot required");ValidatePolicyTimingProtocol();
        var all=new List<Trace>();foreach(string line in TimingLines(Path.Combine(inputFolder,"panel.jsonl.gz")))using(var doc=JsonDocument.Parse(line)) {
            var r=doc.RootElement;all.Add(ParseTrace(r.GetProperty("trace"),r.GetProperty("id").GetString()));
        }
        Need(all.Select(x=>x.Id).SequenceEqual(Panel),"timing input panel/order");var refs=TimingReferences(Path.Combine(inputFolder,"functional-values.jsonl.gz"));
        int samples=0,completeCalls=0,warmCalls=0;bool started=false;long[] zeros=new long[3];
        using(var raw=TimingGzipWriter(Path.Combine(output,"samples.jsonl.gz")))foreach(var original in all) {
            var expected=Expected(original);
            foreach(string policy in Policies)Equal(refs[original.Id+"/"+policy].Values,expected);
            for(int w=0;w<PolicyWarmups;++w)for(int pos=0;pos<Policies.Length;++pos) {
                string policy=Policies[(w+pos)%5];var replay=ReplayPolicy(original,policy);
                ValidateTimedReplay(replay,refs[original.Id+"/"+policy],policy);++warmCalls;
            }
            for(int round=0;round<PolicyRounds;++round)for(int pos=0;pos<Policies.Length;++pos) {
                string policy=Policies[(round+pos)%5];var reference=refs[original.Id+"/"+policy];
                for(int call=0;call<PolicyCalls;++call) {
                    if(!started){markStarted();started=true;} // metadata IO, outside every timer
                    long planner=0,checking=0,complete=0;Trace x=null;Plan plan=null;PolicyReplay replay=null;Exception failure=null;string phase="planner";
                    try {
                        long begin=Stopwatch.GetTimestamp();
                        try{x=WithPrice(original,policy==Policies[4]?FixedVisitPrice:0);plan=BuildPolicy(x,policy);}
                        finally{planner=Stopwatch.GetTimestamp()-begin;}
                        phase="checking";begin=Stopwatch.GetTimestamp();
                        try{Check(x,plan,ExactPolicy(policy));}finally{checking=Stopwatch.GetTimestamp()-begin;}
                        phase="complete";begin=Stopwatch.GetTimestamp();
                        try{replay=ReplayPolicy(original,policy);}finally{complete=Stopwatch.GetTimestamp()-begin;}
                        ++completeCalls;phase="post-timer verification";
                        ValidateTimedReplay(replay,reference,policy);SameCertificate(x,plan,replay.Plan);
                    } catch(Exception e){failure=e;}
                    if(planner==0)++zeros[0];if(checking==0)++zeros[1];if(complete==0)++zeros[2];
                    // All scalar clocks retained, including zero ticks; every completed
                    // timed output checked against the full functional vector above.
                    raw.WriteLine(JsonSerializer.Serialize(new {id=original.Id,round,position=pos,call,policy,
                        planning_visit_weight=policy==Policies[4]?FixedVisitPrice:0,checker=ExactPolicy(policy)?"optimality":"safety-only",
                        frequency=Stopwatch.Frequency,planner_ticks=planner,checking_ticks=checking,complete_ticks=complete,
                        complete_is_phase_sum=false,actual_loads=replay?.Actual.Loads,actual_bytes=replay?.Actual.Bytes,
                        publications=replay?.Actual.Publications,descriptor_copies=replay?.Actual.DescriptorCopies,sink=replay?.Actual.Sink,
                        arena_bytes=replay?.ArenaBytes,functional_reference=original.Id+"/"+policy,
                        complete_values_checked_outside_timer=failure==null,correct=failure==null,failure_phase=failure==null?null:phase,error=failure?.Message}));
                    raw.Flush();++samples;if(failure!=null)throw new InvalidDataException("timed call failed; raw clocks retained",failure);
                }
            }
        }
        Need(samples==3080 && completeCalls==3080 && warmCalls==210,"fixed timing counts");
        File.WriteAllText(Path.Combine(output,"timing-summary.json"),JsonSerializer.Serialize(new {status="TIMING_COMPLETED",panel_cases=14,policies=Policies,
            rounds=PolicyRounds,calls_per_arm=PolicyCalls,warmup_calls=warmCalls,raw_clock_samples=samples,verified_complete_calls=completeCalls,
            zero_tick_calls=new {planner=zeros[0],checking=zeros[1],complete=zeros[2]},performance_measurements_started=started,
            filtering="none",price_tuning=false,seed_selection=false,forced_gc=false,raw_file="samples.jsonl.gz"}));
    }
}
}
