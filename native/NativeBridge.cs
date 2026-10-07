// Original MIT-licensed code; see ../LICENSE. CPU-only, single-threaded.
// Roslyn compiles this harness. allocator.cpp owns all physical buffers/loads.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Runtime.CompilerServices;
using System.Runtime.InteropServices;
using System.Text.Json;
using System.Threading;

namespace P054Native {
public sealed class Page {
    public int Slot, Generation, Content, Group, First, Last, Base, Length, Width;
    public long Weight;
}
public sealed class Trace {
    public string Id = "";
    public int B, A, Heads;
    public long Setup, Rho, Bound;
    public Page[] Pages = Array.Empty<Page>();
    public int[] Frontiers = Array.Empty<int>();
    public int[][] Required = Array.Empty<int[]>();
    public bool[][] Mandatory = Array.Empty<bool[]>(); // unique (p,lane), per step
    public int T { get { return Frontiers.Length; } }
}
public sealed class Epoch {
    public int Start, End;
    public int[] Pages = Array.Empty<int>();
    public long Cost;
}
public sealed class Plan {
    public Epoch[] Epochs = Array.Empty<Epoch>();
    public long[] Potentials = Array.Empty<long>();
    public long Cost;
}
public struct Descriptor {
    public int Page, Slot, Generation, Content, Width, Group, Offset, Length, Start, End;
}
public sealed class Output {
    public int[][] MandatoryValues = Array.Empty<int[]>();
    public long Loads, Bytes, Publications, DescriptorCopies;
    public ulong Sink;
}
public static class Bridge {
    public static readonly string[] Panel = {
        "case-000", "case-001", "case-003", "case-004", "case-005", "case-056",
        "case-120", "case-160", "case-184", "case-196", "case-199",
        "native-wide-repeat", "native-wide-rotate", "native-wide-recycle"
    };
    static void Need(bool ok, string reason) { if (!ok) throw new InvalidDataException(reason); }
    static long Number(JsonElement e, long lo, long hi) {
        long n; Need(e.ValueKind == JsonValueKind.Number && e.TryGetInt64(out n), "integer");
        n = e.GetInt64(); Need(n >= lo && n <= hi, "integer range"); return n;
    }
    static int N(JsonElement e, int lo, int hi) { return (int)Number(e, lo, hi); }
    static void Exact(JsonElement e, params string[] keys) {
        Need(e.ValueKind == JsonValueKind.Object, "object"); var seen = new HashSet<string>();
        foreach (var x in e.EnumerateObject()) Need(seen.Add(x.Name) && keys.Contains(x.Name), "object fields/duplicate");
        Need(seen.Count == keys.Length, "object fields missing");
    }
    static JsonElement[] Array(JsonElement e, int max, int min = 0) {
        Need(e.ValueKind == JsonValueKind.Array && e.GetArrayLength() >= min && e.GetArrayLength() <= max, "array bound");
        return e.EnumerateArray().ToArray();
    }
    static int Width(JsonElement e) {
        Need(e.ValueKind == JsonValueKind.String, "format");
        string f = e.GetString(); Need(f == "int8" || f == "fp16", "format"); return f == "fp16" ? 2 : 1;
    }
    public static int Cap(Trace x, int t, Page p) {
        return (int)Math.Min(p.Length, Math.Max(0L, (long)x.Frontiers[t] - p.Base + 1));
    }
    public static Trace ParseTrace(JsonElement root, string id) {
        Exact(root, "pages", "steps", "setup", "visit_weight", "page_size", "address_bits", "heads");
        var x = new Trace { Id = id, B = N(root.GetProperty("page_size"), 1, 128),
            A = N(root.GetProperty("address_bits"), 1, 64), Heads = N(root.GetProperty("heads"), 1, 32),
            Setup = Number(root.GetProperty("setup"), 0, 1 << 20), Rho = Number(root.GetProperty("visit_weight"), 0, 1 << 20) };
        var steps = Array(root.GetProperty("steps"), 64, 1); var pages = Array(root.GetProperty("pages"), 256, 1);
        x.Pages = new Page[pages.Length]; x.Frontiers = new int[steps.Length];
        x.Required = new int[steps.Length][]; x.Mandatory = new bool[steps.Length][];
        long allWeight = 0;
        for (int i = 0; i < pages.Length; ++i) {
            var q = pages[i]; Exact(q, "slot", "generation", "content", "format", "kv_group", "first", "last", "base", "length", "weight");
            var p = new Page { Slot = N(q.GetProperty("slot"), 0, 255), Generation = N(q.GetProperty("generation"), 1, int.MaxValue),
                Content = N(q.GetProperty("content"), 0, int.MaxValue), Group = N(q.GetProperty("kv_group"), 0, 31),
                First = N(q.GetProperty("first"), 0, steps.Length - 1), Base = N(q.GetProperty("base"), 0, int.MaxValue),
                Length = N(q.GetProperty("length"), 1, x.B), Width = Width(q.GetProperty("format")), Weight = Number(q.GetProperty("weight"), 1, 1 << 20) };
            p.Last = N(q.GetProperty("last"), p.First, steps.Length - 1);
            long end = (long)p.Slot * 2 * x.B + p.Length * p.Width;
            Need(x.A >= 17 || end <= (1L << x.A), "address width"); // max end is 65536; never shift by 64
            x.Pages[i] = p; allWeight += p.Weight;
        }
        foreach (var g in x.Pages.GroupBy(p => p.Slot)) {
            var sorted = g.OrderBy(p => p.First).ToArray();
            for (int j = 1; j < sorted.Length; ++j)
                Need(sorted[j-1].Last < sorted[j].First && sorted[j-1].Generation < sorted[j].Generation, "slot overlap/generation order");
        }
        int nodesTotal = 0, edgesTotal = 0, bindingsTotal = 0;
        for (int t = 0; t < steps.Length; ++t) {
            var s = steps[t]; Exact(s, "frontier", "bindings", "nodes", "roots");
            x.Frontiers[t] = N(s.GetProperty("frontier"), 0, int.MaxValue);
            var bs = Array(s.GetProperty("bindings"), 512); var ns = Array(s.GetProperty("nodes"), 2048); var rs = Array(s.GetProperty("roots"), 2048);
            nodesTotal += ns.Length; bindingsTotal += bs.Length; Need(nodesTotal <= 2048 && bindingsTotal <= 8192, "aggregate bounds");
            var map = new Dictionary<int, int>();
            foreach (var b0 in bs) {
                var b = Array(b0, 6, 6); int h = N(b[0], 0, x.Heads - 1), l = N(b[1], 0, 255), p = N(b[2], 0, pages.Length - 1);
                Need(map.TryAdd(h * 256 + l, p), "duplicate binding"); var m = x.Pages[p];
                Need(N(b[3], 0, int.MaxValue) == m.Content && Width(b[4]) == m.Width && N(b[5], 0, 31) == m.Group, "binding annotations");
                Need(m.First <= t && t <= m.Last, "inactive binding");
            }
            var children = new int[ns.Length][]; var atoms = new int[ns.Length][][];
            for (int j = 0; j < ns.Length; ++j) {
                Exact(ns[j], "children", "atoms");
                children[j] = Array(ns[j].GetProperty("children"), 2048).Select(c => N(c, 0, ns.Length - 1)).ToArray();
                var aa = Array(ns[j].GetProperty("atoms"), 2048); atoms[j] = new int[aa.Length][];
                edgesTotal += children[j].Length + aa.Length; Need(edgesTotal <= 2048, "edge bound");
                for (int k = 0; k < aa.Length; ++k) {
                    var a = Array(aa[k], 4, 4); int h = N(a[0], 0, x.Heads - 1), l = N(a[1], 0, 255);
                    int p; Need(map.TryGetValue(h * 256 + l, out p), "missing binding");
                    int lo = N(a[2], 0, x.B - 1), hi = N(a[3], lo + 1, x.Pages[p].Length);
                    atoms[j][k] = new int[] { p, lo, hi };
                }
            }
            var pending = new Queue<int>(rs.Select(r => N(r, 0, ns.Length - 1))); var seen = new bool[ns.Length];
            var req = new SortedSet<int>(); var lanes = new bool[pages.Length * x.B];
            while (pending.Count > 0) {
                int j = pending.Dequeue(); if (seen[j]) continue; seen[j] = true;
                foreach (int c in children[j]) pending.Enqueue(c);
                foreach (var a in atoms[j]) {
                    Need(a[2] <= Cap(x, t, x.Pages[a[0]]), "causal atom"); req.Add(a[0]);
                    for (int i = a[1]; i < a[2]; ++i) lanes[a[0] * x.B + i] = true;
                }
            }
            x.Required[t] = req.ToArray(); x.Mandatory[t] = lanes;
        }
        x.Bound = checked(x.T * (x.Setup + (1 + x.Rho * x.T) * allWeight));
        return x;
    }
    static int[] Union(Trace x, int s, int t) {
        var selected = new SortedSet<int>(); for (int q = s; q <= t; ++q) selected.UnionWith(x.Required[q]); return selected.ToArray();
    }
    static bool Feasible(Trace x, int[] u, int s, int t) { return u.All(p => x.Pages[p].First <= s && t <= x.Pages[p].Last); }
    static long Cost(Trace x, int[] u, int s, int t) { return checked(x.Setup + (1 + x.Rho * (t-s+1)) * u.Sum(p => x.Pages[p].Weight)); }
    public static Plan Fresh(Trace x) {
        var es = new Epoch[x.T]; long cost = 0;
        for (int t = 0; t < x.T; ++t) { es[t] = new Epoch { Start = t, End = t, Pages = x.Required[t].ToArray(), Cost = Cost(x, x.Required[t], t, t) }; cost += es[t].Cost; }
        return new Plan { Epochs = es, Cost = cost };
    }
    // Transparent native direct DP, not the Python range-tree producer. Its cost is timed separately.
    public static Plan Produce(Trace x) {
        var d = new long[x.T+1]; var parent = new int[x.T+1];
        for (int t = 0; t < x.T; ++t) {
            d[t+1] = long.MaxValue;
            for (int s = 0; s <= t; ++s) {
                var u = Union(x, s, t); if (!Feasible(x, u, s, t)) continue;
                long value = checked(d[s] + Cost(x, u, s, t));
                if (value < d[t+1]) { d[t+1] = value; parent[t+1] = s; }
            }
        }
        var es = new List<Epoch>(); int end = x.T;
        while (end > 0) { int start = parent[end]; var u = Union(x, start, end-1); es.Add(new Epoch { Start = start, End = end-1, Pages = u, Cost = Cost(x,u,start,end-1) }); end = start; }
        es.Reverse(); return new Plan { Epochs = es.ToArray(), Potentials = d, Cost = d[x.T] };
    }
    public static Plan ParsePlan(Trace x, JsonElement c) {
        Exact(c,"epochs","potentials","frontiers","total_cost");
        var fs = Array(c.GetProperty("frontiers"), x.T, x.T);
        for (int t=0; t<x.T; ++t) Need(N(fs[t],0,int.MaxValue)==x.Frontiers[t],"frontier mismatch");
        var plan = new Plan { Cost = Number(c.GetProperty("total_cost"),0,x.Bound),
            Potentials = Array(c.GetProperty("potentials"),x.T+1,x.T+1).Select(v=>Number(v,0,x.Bound)).ToArray() };
        var es = Array(c.GetProperty("epochs"),x.T,1); plan.Epochs = new Epoch[es.Length];
        for (int j=0; j<es.Length; ++j) {
            var e=es[j]; Exact(e,"start","end","pages","cost"); int s=N(e.GetProperty("start"),0,x.T-1), t=N(e.GetProperty("end"),s,x.T-1);
            var selected=new List<int>(); int prior=-1;
            foreach(var desc in Array(e.GetProperty("pages"),x.Pages.Length)) {
                var v=Array(desc,6,6); int p=N(v[0],0,x.Pages.Length-1); Need(p>prior,"descriptor order"); prior=p; var m=x.Pages[p];
                Need(N(v[1],0,int.MaxValue)==m.Slot && N(v[2],0,int.MaxValue)==m.Generation && N(v[3],0,int.MaxValue)==m.Content && Width(v[4])==m.Width && N(v[5],0,int.MaxValue)==m.Group,"descriptor mismatch");
                selected.Add(p);
            }
            plan.Epochs[j]=new Epoch {Start=s,End=t,Pages=selected.ToArray(),Cost=Number(e.GetProperty("cost"),0,x.Bound)};
        }
        Check(x,plan,true); return plan;
    }
    // Independent of Produce/Union: bitmap interval enumeration and telescoping potentials.
    public static void Check(Trace x, Plan plan, bool optimal) {
        Need(plan.Epochs.Length>=1 && plan.Epochs.Length<=x.T,"epoch count"); int next=0; long total=0;
        foreach (var e in plan.Epochs) {
            Need(e.Start==next && e.End>=e.Start && e.End<x.T,"partition"); next=e.End+1;
            var have=new bool[x.Pages.Length]; int prior=-1; long weight=0;
            foreach (int p in e.Pages) {
                Need(p>=0 && p<x.Pages.Length && p>prior,"selected range/order"); prior=p; have[p]=true; var m=x.Pages[p];
                Need(m.First<=e.Start && e.End<=m.Last,"lease lifetime"); weight+=m.Weight;
            }
            var need=new bool[x.Pages.Length]; for(int t=e.Start;t<=e.End;++t) foreach(int p in x.Required[t]) need[p]=true;
            for(int p=0;p<have.Length;++p) Need(!need[p]||have[p],"coverage");
            if(optimal) Need(have.SequenceEqual(need),"canonical list");
            Need(e.Cost==checked(x.Setup+(1+x.Rho*(e.End-e.Start+1))*weight),"epoch cost"); total=checked(total+e.Cost);
        }
        Need(next==x.T && total==plan.Cost && total<=x.Bound,"total/partition end");
        if(!optimal)return;
        var d=plan.Potentials; Need(d.Length==x.T+1 && d[0]==0 && d.All(v=>v>=0&&v<=x.Bound),"potential range");
        for(int t=0;t<x.T;++t) {
            var seen=new bool[x.Pages.Length]; long weight=0; int first=0,last=x.T-1;
            for(int s=t;s>=0;--s) {
                foreach(int p in x.Required[s]) if(!seen[p]) { seen[p]=true; var m=x.Pages[p];weight+=m.Weight;first=Math.Max(first,m.First);last=Math.Min(last,m.Last); }
                if(first<=s && t<=last) Need(d[t+1]<=checked(d[s]+x.Setup+(1+x.Rho*(t-s+1))*weight),"dual inequality");
            }
        }
        Need(d[x.T]==total,"primal dual gap");
    }
    public static object Certificate(Trace x, Plan plan) {
        return new { epochs=plan.Epochs.Select(e=>new { start=e.Start,end=e.End,cost=e.Cost,
            pages=e.Pages.Select(p=>new object[]{p,x.Pages[p].Slot,x.Pages[p].Generation,x.Pages[p].Content,x.Pages[p].Width==2?"fp16":"int8",x.Pages[p].Group}).ToArray() }).ToArray(),
            potentials=plan.Potentials,frontiers=x.Frontiers,total_cost=plan.Cost };
    }
    // Synthetic bit patterns, not numerical fp16 attention. int8 is also compared as raw bits.
    public static int Payload(Page p,int lane) {
        ulong v=unchecked((ulong)p.Content*131UL+(ulong)p.Generation*17UL+(ulong)p.Group*7UL+(ulong)lane*29UL);
        return (int)(v & (p.Width==2 ? 65535UL : 255UL));
    }
    public static int[][] Expected(Trace x) {
        var result=new int[x.T][];
        for(int t=0;t<x.T;++t) { var values=new List<int>(); for(int p=0;p<x.Pages.Length;++p) for(int i=0;i<x.B;++i)
            if(x.Mandatory[t][p*x.B+i]) values.Add(Payload(x.Pages[p],i)); result[t]=values.ToArray(); }
        return result;
    }
    public static void Equal(int[][] a,int[][] b) { Need(a.Length==b.Length,"output steps");for(int t=0;t<a.Length;++t)Need(a[t].SequenceEqual(b[t]),"actual mandatory values differ"); }
    [StructLayout(LayoutKind.Sequential)] struct NativePage { public int Slot,Generation,Content,Group,First,Last,Base,Length,Width; }
    [StructLayout(LayoutKind.Sequential)] struct NativeEpoch { public int Start,End,Offset,Count; }
    [StructLayout(LayoutKind.Sequential)] struct NativeCounts { public long Loads,Bytes,Publications,Copies; public ulong Sink; }
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate void Observer(int kind,int t,int p,int slot,int generation,int lane,int width,int offset,int value,int start,int end,ulong address);
    static class Native {
        [DllImport("p054_allocator",CallingConvention=CallingConvention.Cdecl)] internal static extern IntPtr nb_create(int B,int A,int T,int P,NativePage[] pages,int[] frontiers,byte[] masks,byte[] err,int cap);
        [DllImport("p054_allocator",CallingConvention=CallingConvention.Cdecl)] internal static extern int nb_run(IntPtr context,NativeEpoch[] epochs,int E,Descriptor[] descriptors,int D,[Out] uint[] output,out NativeCounts counts,Observer observe,byte[] err,int cap);
        [DllImport("p054_allocator",CallingConvention=CallingConvention.Cdecl)] internal static extern int nb_batch(IntPtr context,NativeEpoch[] epochs,int E,Descriptor[] descriptors,int D,[Out] uint[] output,out NativeCounts counts,int repeats,out long ns,byte[] err,int cap);
        [DllImport("p054_allocator",CallingConvention=CallingConvention.Cdecl)] internal static extern int nb_guards(IntPtr context,byte[] err,int cap);
        [DllImport("p054_allocator",CallingConvention=CallingConvention.Cdecl)] internal static extern int nb_selftest(IntPtr context,byte[] err,int cap);
        [DllImport("p054_allocator",CallingConvention=CallingConvention.Cdecl)] internal static extern int nb_emptytest(IntPtr context,byte[] err,int cap);
        [DllImport("p054_allocator",CallingConvention=CallingConvention.Cdecl)] internal static extern void nb_destroy(IntPtr context);
    }
    public static void LoadNative(string path) {
        IntPtr handle=NativeLibrary.Load(Path.GetFullPath(path));
        NativeLibrary.SetDllImportResolver(typeof(Bridge).Assembly,(name,assembly,search)=>name=="p054_allocator"?handle:IntPtr.Zero);
        Need(Marshal.SizeOf<NativePage>()==36&&Marshal.SizeOf<NativeEpoch>()==16&&Marshal.SizeOf<Descriptor>()==40&&Marshal.SizeOf<NativeCounts>()==40,"native ABI sizes");
    }
    public sealed class Arena : IDisposable {
        readonly Trace x;readonly IntPtr context;readonly uint[] flat;readonly int[][] outputs;bool disposed;
        readonly Dictionary<Plan,(NativeEpoch[],Descriptor[],int)> plans=new Dictionary<Plan,(NativeEpoch[],Descriptor[],int)>();
        public int ArenaBytes {get{return (x.Pages.Max(p=>p.Slot)+1)*2*x.B;}}
        static void Status(int status,byte[] error){Need(status==0,"native: "+System.Text.Encoding.UTF8.GetString(error).TrimEnd('\0'));}
        public Arena(Trace trace){x=trace;var pages=x.Pages.Select(m=>new NativePage {Slot=m.Slot,Generation=m.Generation,Content=m.Content,Group=m.Group,First=m.First,Last=m.Last,Base=m.Base,Length=m.Length,Width=m.Width}).ToArray();
            var error=new byte[256];context=Native.nb_create(x.B,x.A,x.T,x.Pages.Length,pages,x.Frontiers,x.Mandatory.SelectMany(m=>m.Select(b=>(byte)(b?1:0))).ToArray(),error,error.Length);Status(context==IntPtr.Zero?1:0,error);
            flat=new uint[x.T*x.Pages.Length*x.B];outputs=Enumerable.Range(0,x.T).Select(t=>new int[x.Mandatory[t].Count(b=>b)]).ToArray();}
        public void Prepare(Plan plan){if(plans.ContainsKey(plan))return;var ds=new List<Descriptor>();var es=new List<NativeEpoch>();
            foreach(var e in plan.Epochs){es.Add(new NativeEpoch {Start=e.Start,End=e.End,Offset=ds.Count,Count=e.Pages.Length});foreach(int p in e.Pages){var m=x.Pages[p];ds.Add(new Descriptor {Page=p,Slot=m.Slot,Generation=m.Generation,Content=m.Content,Width=m.Width,Group=m.Group,Offset=m.Slot*2*x.B,Length=m.Length,Start=e.Start,End=e.End});}}
            int count=ds.Count;plans.Add(plan,(es.ToArray(),ds.ToArray(),count));}
        public Output Execute(Plan plan,Action<object> audit=null){Prepare(plan);var args=plans[plan];var error=new byte[256];Observer observe=null;
            if(audit!=null)observe=(kind,t,p,slot,generation,lane,width,offset,value,start,end,address)=>audit(new {kind=new[]{"retire","activate","publish","consult","load"}[kind],step=t,page=p,slot,generation,lane,width,offset,value,start,end,address=address.ToString("x")});
            NativeCounts c;Status(Native.nb_run(context,args.Item1,args.Item1.Length,args.Item2,args.Item3,flat,out c,observe,error,error.Length),error);
            for(int t=0;t<x.T;++t){int j=0;for(int k=0;k<x.Mandatory[t].Length;++k)if(x.Mandatory[t][k])outputs[t][j++]=(int)flat[t*x.Pages.Length*x.B+k];}
            GC.KeepAlive(observe);return new Output {MandatoryValues=outputs,Loads=c.Loads,Bytes=c.Bytes,Publications=c.Publications,DescriptorCopies=c.Copies,Sink=c.Sink};}
        public Output Batch(Plan plan,int repeats,out long nativeNs){Prepare(plan);var args=plans[plan];var error=new byte[256];NativeCounts c;
            Status(Native.nb_batch(context,args.Item1,args.Item1.Length,args.Item2,args.Item3,flat,out c,repeats,out nativeNs,error,error.Length),error);
            for(int t=0;t<x.T;++t){int j=0;for(int k=0;k<x.Mandatory[t].Length;++k)if(x.Mandatory[t][k])outputs[t][j++]=(int)flat[t*x.Pages.Length*x.B+k];}
            return new Output {MandatoryValues=outputs,Loads=c.Loads,Bytes=c.Bytes,Publications=c.Publications,DescriptorCopies=c.Copies,Sink=c.Sink};}
        public void Guards(){var error=new byte[256];Status(Native.nb_guards(context,error,error.Length),error);}
        public void RejectionTests(){var error=new byte[256];Status(Native.nb_selftest(context,error,error.Length),error);}
        public void EmptyNullTest(){var error=new byte[256];Status(Native.nb_emptytest(context,error,error.Length),error);}
        public void Dispose(){if(!disposed){try{Guards();}finally{Native.nb_destroy(context);disposed=true;}}}
    }
    static void Rejected(Action f){bool rejected=false;try{f();}catch(InvalidDataException){rejected=true;}Need(rejected,"negative control accepted");}
    static List<Trace> LoadTraces(string file) {
        Need(new FileInfo(file).Length<=4*1024*1024,"corpus file bound");var all=new List<Trace>();
        foreach(string line in File.ReadLines(file)){using(var doc=JsonDocument.Parse(line)){var root=doc.RootElement;all.Add(ParseTrace(root.GetProperty("trace"),root.GetProperty("id").GetString()));}Need(all.Count<=200,"corpus count");}
        Need(all.Count==200&&all.Select(x=>x.Id).Distinct().Count()==200,"frozen corpus identity");return all;
    }
    static Dictionary<string,JsonElement> LoadCertificates(string file) {
        Need(new FileInfo(file).Length<=4*1024*1024,"certificate corpus file bound");var result=new Dictionary<string,JsonElement>();
        foreach(string line in File.ReadLines(file))using(var doc=JsonDocument.Parse(line))result.Add(doc.RootElement.GetProperty("id").GetString(),doc.RootElement.GetProperty("certificate").Clone());return result;
    }
    public static Trace Synthetic(string id) {
        bool recycle=id=="native-wide-recycle", rotate=id=="native-wide-rotate";
        int P=recycle?32:rotate?32:16,T=64,B=128;var pages=new object[P];var steps=new object[T];
        for(int p=0;p<P;++p)pages[p]=new {slot=recycle?p%8:p,generation=recycle?p/8+1:1,content=5000+p,format=p%2==0?"fp16":"int8",kv_group=p%4,
            first=recycle?(p/8)*16:0,last=recycle?(p/8+1)*16-1:T-1,@base=0,length=B,weight=1};
        for(int t=0;t<T;++t){var need=recycle?new int[]{(t/16)*8+t%8,(t/16)*8+(t+1)%8}:rotate?new int[]{t%P}:Enumerable.Range(0,P).ToArray();
            steps[t]=new {frontier=B-1,bindings=need.Select(p=>new object[]{0,p,p,5000+p,p%2==0?"fp16":"int8",p%4}).ToArray(),
                nodes=new[]{new {children=System.Array.Empty<int>(),atoms=need.Select(p=>new int[]{0,p,0,B}).ToArray()}},roots=new[]{0}};}
        using(var doc=JsonDocument.Parse(JsonSerializer.Serialize(new {pages,steps,setup=1,visit_weight=0,page_size=B,address_bits=16,heads=1})))return ParseTrace(doc.RootElement,id);
    }
    public static Trace Edge(string id) {
        bool zero=id=="native-edge-capzero",empty=id=="native-edge-empty",max=id=="native-edge-maxcost";
        int T=zero?3:empty?4:max?64:1,B=zero||empty?4:128,P=zero?2:max?256:1;
        var pages=new object[P];var steps=new object[T];
        for(int p=0;p<P;++p)pages[p]=new {slot=zero||empty?p:max?p:255,generation=int.MaxValue,content=int.MaxValue-p,format=p%2==0?"fp16":"int8",kv_group=31,
            first=zero&&p==1?1:0,last=T-1,@base=zero?(p==1?100:0):empty?0:int.MaxValue-127,length=B,weight=max?1<<20:1};
        for(int t=0;t<T;++t){int p=zero&&t==1?1:0;int[] need=empty?System.Array.Empty<int>():new[]{p};
            steps[t]=new {frontier=zero?(t==1?100:0):empty?0:int.MaxValue,
                bindings=need.Select(q=>new object[]{0,q,q,int.MaxValue-q,q%2==0?"fp16":"int8",31}).ToArray(),
                nodes=new[]{new {children=System.Array.Empty<int>(),atoms=need.Select(q=>new int[]{0,q,0,zero?1:B}).ToArray()}},roots=new[]{0}};}
        using(var doc=JsonDocument.Parse(JsonSerializer.Serialize(new {pages,steps,setup=empty?0:max?1<<20:100,visit_weight=max?1<<20:0,page_size=B,address_bits=64,heads=1})))return ParseTrace(doc.RootElement,id);
    }
    public static void Conformance(string root,string output) {
        Directory.CreateDirectory(output);var all=LoadTraces(Path.Combine(root,"inputs","traces.jsonl"));var saved=LoadCertificates(Path.Combine(root,"results","campaign","certificates.jsonl"));
        all.AddRange(new[]{Synthetic("native-wide-repeat"),Synthetic("native-wide-rotate"),Synthetic("native-wide-recycle")});
        all.AddRange(new[]{Edge("native-edge-capzero"),Edge("native-edge-empty"),Edge("native-edge-address64"),Edge("native-edge-maxcost")});
        using(var observations=new StreamWriter(Path.Combine(output,"observations.jsonl")))using(var rows=new StreamWriter(Path.Combine(output,"conformance.jsonl"))) {
            foreach(var x in all){var plan=Produce(x);Check(x,plan,true);var baseline=Fresh(x);Check(x,baseline,false);
                if(saved.ContainsKey(x.Id))Need(ParsePlan(x,saved[x.Id]).Cost==plan.Cost,"frozen optimum agreement");
                var expected=Expected(x);var actual=new List<object>();
                foreach(var item in new[]{("baseline",baseline),("certified",plan)})using(var arena=new Arena(x)){
                    bool audit=Panel.Contains(x.Id)||x.Id.StartsWith("native-edge-");Action<object> observe=audit?(Action<object>)(ev=>observations.WriteLine(JsonSerializer.Serialize(new {id=x.Id,mode=item.Item1,ev}))):null;
                    var result=arena.Execute(item.Item2,observe);Equal(result.MandatoryValues,expected);arena.Guards();
                    actual.Add(new {mode=item.Item1,values=result.MandatoryValues,loads=result.Loads,bytes=result.Bytes,publications=result.Publications,descriptor_copies=result.DescriptorCopies,sink=result.Sink,arena_bytes=arena.ArenaBytes});
                }
                rows.WriteLine(JsonSerializer.Serialize(new {id=x.Id,trace=x.Id.StartsWith("native-")?TraceObject(x):null,certificate=Certificate(x,plan),actual,expected,passed=true}));rows.Flush();
            }
            using(var arena=new Arena(all[0]))arena.RejectionTests();
            using(var arena=new Arena(all.Single(x=>x.Id=="native-edge-empty")))arena.EmptyNullTest();
        }
        Need(new FileInfo(Path.Combine(output,"observations.jsonl")).Length<256*1024*1024,"audit output bound");
        int mutants=0;using(var rows=new StreamWriter(Path.Combine(output,"native-checker-mutants.jsonl"))){
            string file=Path.Combine(root,"results","campaign","mutations.jsonl");Need(new FileInfo(file).Length<=4*1024*1024,"mutation file bound");
            foreach(string line in File.ReadLines(file))using(var doc=JsonDocument.Parse(line)){var r=doc.RootElement;bool rejected=false;string reason="";
                try{var x=ParseTrace(r.GetProperty("trace"),r.GetProperty("id").GetString());ParsePlan(x,r.GetProperty("certificate"));}catch(InvalidDataException e){rejected=true;reason=e.Message;}
                Need(rejected,"frozen mutant accepted by native harness checker");++mutants;rows.WriteLine(JsonSerializer.Serialize(new {id=r.GetProperty("id").GetString(),rejected,reason}));}
        }Need(mutants==400,"mutation count");
        File.WriteAllText(Path.Combine(output,"summary.json"),JsonSerializer.Serialize(new {status="CONFORMANCE_PASSED",cases=all.Count,frozen_optima=200,native_checker_mutants=mutants,native_resident_negative_controls=4,null_descriptor_empty_trace_passed=true,panel=Panel,performance_measurements_started=false}));
    }
    static IEnumerable<int[]> AtomIntervals(Trace x,int t,int p) {
        int i=0;while(i<x.B){if(!x.Mandatory[t][p*x.B+i]){++i;continue;}int lo=i;
            while(i<x.B&&x.Mandatory[t][p*x.B+i])++i;yield return new[]{0,p,lo,i};}
    }
    public static object TraceObject(Trace x) {
        // For synthetic cases, reconstruct the exact constructor input, not a runtime log as authority.
        return new {pages=x.Pages.Select(p=>new {slot=p.Slot,generation=p.Generation,content=p.Content,format=p.Width==2?"fp16":"int8",kv_group=p.Group,first=p.First,last=p.Last,@base=p.Base,length=p.Length,weight=p.Weight}).ToArray(),
            steps=Enumerable.Range(0,x.T).Select(t=>new {frontier=x.Frontiers[t],bindings=x.Required[t].Select(p=>new object[]{0,p,p,x.Pages[p].Content,x.Pages[p].Width==2?"fp16":"int8",x.Pages[p].Group}).ToArray(),nodes=new[]{new {children=System.Array.Empty<int>(),atoms=x.Required[t].SelectMany(p=>AtomIntervals(x,t,p)).ToArray()}},roots=new[]{0}}).ToArray(),setup=x.Setup,visit_weight=x.Rho,page_size=x.B,address_bits=x.A,heads=x.Heads};
    }
    // Called ONLY by the reserved-slot branch of run.ps1. Fixed repeats; no outcome-based tuning.
    public static void Measure(string root,string output) {
        var all=LoadTraces(Path.Combine(root,"inputs","traces.jsonl"));all.AddRange(new[]{Synthetic("native-wide-repeat"),Synthetic("native-wide-rotate"),Synthetic("native-wide-recycle")});
        const int pairs=11, repeats=8; Directory.CreateDirectory(output);
        using(var raw=new StreamWriter(Path.Combine(output,"samples.jsonl")))foreach(string id in Panel){var x=all.Single(v=>v.Id==id);var expected=Expected(x);
            // Exactly two untimed warmups of BOTH setup/check/execution paths for each case.
            for(int w=0;w<2;++w){var b=Fresh(x);Check(x,b,false);var c=Produce(x);Check(x,c,true);using(var a=new Arena(x)){Equal(a.Execute(b).MandatoryValues,expected);Equal(a.Execute(c).MandatoryValues,expected);}}
            for(int pair=0;pair<pairs;++pair){foreach(string mode in (pair%2==0?new[]{"baseline","certified"}:new[]{"certified","baseline"})){
                // Frozen JSON decoding is outside the repeated blocks; native planner and checker are included below.
                Plan plan=null;long begin=Stopwatch.GetTimestamp();for(int r=0;r<repeats;++r)plan=mode=="baseline"?Fresh(x):Produce(x);long setup=Stopwatch.GetTimestamp()-begin;
                begin=Stopwatch.GetTimestamp();for(int r=0;r<repeats;++r)Check(x,plan,mode=="certified");long checking=Stopwatch.GetTimestamp()-begin;
                begin=Stopwatch.GetTimestamp();var arena=new Arena(x);long allocation=Stopwatch.GetTimestamp()-begin;
                Output result=null;long execution,nativeNs,adapter;using(arena){begin=Stopwatch.GetTimestamp();arena.Prepare(plan);adapter=Stopwatch.GetTimestamp()-begin;
                    begin=Stopwatch.GetTimestamp();result=arena.Batch(plan,repeats,out nativeNs);execution=Stopwatch.GetTimestamp()-begin;arena.Guards();Equal(result.MandatoryValues,expected);}
                // A genuinely measured full path from the decoded input, not a sum of phase counters.
                // This includes one plan/check, allocation, adapter, native execution, projection and free.
                Output oneResult;begin=Stopwatch.GetTimestamp();var onePlan=mode=="baseline"?Fresh(x):Produce(x);Check(x,onePlan,mode=="certified");
                using(var oneArena=new Arena(x)){oneArena.Prepare(onePlan);oneResult=oneArena.Execute(onePlan);}
                long complete=Stopwatch.GetTimestamp()-begin;Equal(oneResult.MandatoryValues,expected);Equal(result.MandatoryValues,oneResult.MandatoryValues);
                // A non-timed full byte-result gate for EVERY sample; value arrays are retained, not only a hash.
                raw.WriteLine(JsonSerializer.Serialize(new {id,pair,mode,repeats,frequency=Stopwatch.Frequency,setup_ticks=setup,checking_ticks=checking,allocation_ticks=allocation,adapter_ticks=adapter,execution_ticks=execution,native_execution_ns=nativeNs,complete_from_decoded_trace_ticks=complete,
                    actual_values=result.MandatoryValues,actual_loads=result.Loads,actual_bytes=result.Bytes,publications=result.Publications,descriptor_copies=result.DescriptorCopies,sink=result.Sink,correct=true}));raw.Flush();
            }}
        }
    }
}
}
