// Bounded owned semantic controls, not timings. MIT; see ../LICENSE.
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;

namespace P054Native {
public static partial class Bridge {
    static Trace PolicyControl(string id,int[][] needs,int[] first,int[] last,long[] weights,long setup) {
        var pages=weights.Select((w,p)=>new {slot=p,generation=1,content=p+100,format=p%2==0?"fp16":"int8",kv_group=0,
            first=first[p],last=last[p],@base=0,length=4,weight=w}).ToArray();
        var steps=needs.Select(need=>new {frontier=3,
            bindings=need.Select(p=>new object[]{0,p,p,p+100,p%2==0?"fp16":"int8",0}).ToArray(),
            nodes=new[]{new {children=new[]{0},atoms=need.Select(p=>new[]{0,p,0,1}).ToArray()}},roots=new[]{0}}).ToArray();
        using(var doc=JsonDocument.Parse(JsonSerializer.Serialize(new {pages,steps,setup,visit_weight=0,page_size=4,address_bits=16,heads=1})))
            return ParseTrace(doc.RootElement,id);
    }
    static void CheckPolicyControl(Trace x) {
        var a=ProduceRangeMin(x);Check(x,a,true);SameCertificate(x,a,Produce(x));SameCertificate(x,a,ProduceReference(x));
        foreach(long price in new long[]{1,3,1<<20}) {var y=WithPrice(x,price);var b=Produce(y);Check(y,b,true);SameCertificate(y,b,ProduceReference(y));}
        foreach(var plan in new[]{Fresh(x),LongestFeasible(x),FourStep(x)}) {
            Need(plan.Potentials.Length==0,"heuristic manufactured potentials");Check(x,plan,false);
        }
    }
    static int RunPolicyTests() {
        // Test all tree primitives against a leaf array, including replacement
        // after lazy additions, singleton/full ranges, empty additions and ties.
        const long inf=1000000;var tree=new RangeMin(9,inf);var leaves=Enumerable.Repeat(4L,9).ToArray();
        for(int k=0;k<9;++k)tree.Set(k,leaves[k]);
        var random=new Random(20261012);
        for(int i=0;i<200;++i) {
            int a=random.Next(9),b=random.Next(a,9);
            if(i%3==0){long v=random.Next(30);tree.Set(a,v);leaves[a]=v;}
            else {long delta=random.Next(7);tree.Add(a,b,delta);for(int k=a;k<=b;++k)leaves[k]+=delta;}
            tree.Add(4,3,99);
            for(int s=0;s<9;++s)for(int t=s;t<9;++t) {
                int arg=s;for(int k=s+1;k<=t;++k)if(leaves[k]<leaves[arg])arg=k;
                Need(tree.Min(s,t)==(leaves[arg],arg),"range tree primitive/tie test");
            }
        }
        var empty=PolicyControl("test-empty-tie",Enumerable.Range(0,5).Select(t=>System.Array.Empty<int>()).ToArray(),new[]{0},new[]{4},new long[]{1},0);
        var tie=ProduceRangeMin(empty);Need(tie.Epochs.Length==1 && tie.Epochs[0].Start==0 && tie.Cost==0 && tie.Potentials.All(v=>v==0),"empty earliest-start tie");
        var repeated=PolicyControl("test-repeated-tie",new[]{new[]{0},new[]{0},new[]{0}},new[]{0},new[]{2},new long[]{2},0);
        Need(ProduceRangeMin(repeated).Epochs.Length==1,"repeated earliest-start tie");
        var expiry=PolicyControl("test-unused-expiry",new[]{new[]{0},new[]{0},new[]{0}},new[]{0,0},new[]{2,0},new long[]{2,9},1);
        Need(ProduceRangeMin(expiry).Epochs.Length==1,"unused expiry must not advance lower frontier");
        // Birth at 2 splits [0,1]; the next four-step cap remains 3, not 5.
        var anchored=PolicyControl("test-anchor-after-birth",new[]{new[]{0},new[]{0},new[]{1},new[]{1},new[]{1},new[]{1}},
            new[]{0,2},new[]{5,5},new long[]{1,1},1);
        var four=FourStep(anchored);Need(four.Epochs.Select(e=>e.End).SequenceEqual(new[]{1,3,5}),"four-step anchoring");
        // A late-born page no longer needed still constrains later feasible starts.
        var birth=PolicyControl("test-persistent-birth",new[]{new[]{0},new[]{1},System.Array.Empty<int>(),new[]{0}},
            new[]{0,1},new[]{3,3},new long[]{1,2},4);
        var gap=PolicyControl("test-greedy-gap",new[]{new[]{0},new[]{1},new[]{1}},new[]{0,0},new[]{1,2},new long[]{1,1024},1);
        Need(LongestFeasible(gap).Cost==2051 && ProduceRangeMin(gap).Cost==1027,"greedy counterexample accounting");
        var controls=new List<Trace>{empty,repeated,expiry,anchored,birth,gap};
        for(int i=0;i<128;++i) {
            int T=1+random.Next(5),P=1+random.Next(4);var first=new int[P];var last=new int[P];var weight=new long[P];
            for(int p=0;p<P;++p){first[p]=random.Next(T);last[p]=random.Next(first[p],T);weight[p]=1+random.Next(4);}
            var needs=Enumerable.Range(0,T).Select(t=>Enumerable.Range(0,P).Where(p=>first[p]<=t && t<=last[p] && random.Next(2)==1).ToArray()).ToArray();
            controls.Add(PolicyControl("test-finite-"+i,needs,first,last,weight,i%4));
        }
        foreach(var x in controls)CheckPolicyControl(x);
        Rejected(()=>ProduceRangeMin(WithPrice(empty,1)));
        // A safe suboptimum must pass safety without optimality potentials.
        Check(gap,LongestFeasible(gap),false);Rejected(()=>Check(gap,LongestFeasible(gap),true));
        return controls.Count;
    }
}
}
