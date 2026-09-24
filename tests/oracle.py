"""Tiny exhaustive oracle: bit-vector page selections and cut masks, not dynamic programming."""
from __future__ import annotations


def analyze(trace):
    n=len(trace['steps']);P=len(trace['pages']);assert n<=5 and P<=4
    required=[]
    for st in trace['steps']:
        # Boolean transitive closure, deliberately unlike both executable graph traversals.
        N=len(st['nodes']);reach=[[i==j or j in st['nodes'][i]['children'] for j in range(N)] for i in range(N)]
        for k in range(N):
            for i in range(N):
                for j in range(N):reach[i][j]=reach[i][j] or (reach[i][k] and reach[k][j])
        bits=0
        for i,node in enumerate(st['nodes']):
            if any(reach[r][i] for r in st['roots']):
                for h,l,lo,hi in node['atoms']:
                    if lo<hi:
                        candidates=[b[2] for b in st['bindings'] if b[0]==h and b[1]==l]
                        assert len(candidates)==1;bits|=1<<candidates[0]
        required.append(bits)
    cost={};choices=0
    for s in range(n):
        u=0
        for t in range(s,n):
            u|=required[t];valid=[]
            for selected in range(1<<P):
                choices+=1
                if selected & u != u:continue
                if any((selected>>p)&1 and not (x['first']<=s and t<=x['last']) for p,x in enumerate(trace['pages'])):continue
                weight=sum(x['weight'] for p,x in enumerate(trace['pages']) if (selected>>p)&1)
                v=trace['setup']+(1+trace['visit_weight']*(t-s+1))*weight
                valid.append((v,selected))
            if valid:
                best=min(v for v,m in valid);minimizers=[m for v,m in valid if v==best]
                assert minimizers==[u],('nonunique minimum',s,t,minimizers,u)
                cost[s,t]=best
    values=[]
    for cut in range(1<<(n-1)):
        choices+=1;s=0;v=0;ok=True
        for t in range(n):
            if t==n-1 or cut>>t&1:
                if (s,t) not in cost:ok=False;break
                v+=cost[s,t];s=t+1
        if ok:values.append(v)
    return {'cost':min(values),'obligations':choices,'intervals':len(cost)}
