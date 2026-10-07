"""Untrusted producer for finite, generation-aware page-list reuse certificates.

Only JSON is shared with checker.py.  The producer uses a last-use segment tree;
the checker deliberately uses direct interval unions instead.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Any


def requirements(trace: dict[str, Any]) -> list[set[int]]:
    result=[]
    for st in trace['steps']:
        mapping={(b[0],b[1]):b[2] for b in st['bindings']}
        seen=set(); stack=list(st['roots']); need=set()
        while stack:
            i=stack.pop()
            if i in seen: continue
            seen.add(i); node=st['nodes'][i]
            stack.extend(node['children'])
            for h,l,lo,hi in node['atoms']:
                if lo<hi: need.add(mapping[h,l])
        result.append(need)
    return result


class RangeMin:
    """Range addition, point replacement and range-minimum with a stable tie rule."""
    def __init__(self,n:int,inf:int):
        self.n=n; self.inf=inf
        self.val=[inf]*(4*n); self.arg=[0]*(4*n); self.lazy=[0]*(4*n)
        def init(v,l,r):
            self.arg[v]=l
            if l<r:
                m=(l+r)//2;init(v*2,l,m);init(v*2+1,m+1,r)
        init(1,0,n-1)
    def _put(self,v:int,d:int):
        self.val[v]+=d;self.lazy[v]+=d
    def _push(self,v:int):
        if self.lazy[v]:
            self._put(v*2,self.lazy[v]);self._put(v*2+1,self.lazy[v]);self.lazy[v]=0
    def _pull(self,v:int):
        a,b=v*2,v*2+1
        j=a if (self.val[a],self.arg[a])<=(self.val[b],self.arg[b]) else b
        self.val[v],self.arg[v]=self.val[j],self.arg[j]
    def set(self,i:int,x:int):
        def go(v,l,r):
            if l==r:self.val[v]=x;self.lazy[v]=0;return
            self._push(v);m=(l+r)//2
            if i<=m:go(v*2,l,m)
            else:go(v*2+1,m+1,r)
            self._pull(v)
        go(1,0,self.n-1)
    def add(self,a:int,b:int,d:int):
        def go(v,l,r):
            if b<l or r<a:return
            if a<=l and r<=b:self._put(v,d);return
            self._push(v);m=(l+r)//2;go(v*2,l,m);go(v*2+1,m+1,r);self._pull(v)
        if a<=b:go(1,0,self.n-1)
    def min(self,a:int,b:int)->tuple[int,int]:
        def go(v,l,r):
            if b<l or r<a:return self.inf,self.n
            if a<=l and r<=b:return self.val[v],self.arg[v]
            self._push(v);m=(l+r)//2
            return min(go(v*2,l,m),go(v*2+1,m+1,r))
        return go(1,0,self.n-1)


def span(trace:dict[str,Any], req:list[set[int]],s:int,t:int, *,
         ignore_birth:bool=False,ignore_death:bool=False)->tuple[int,set[int]]|None:
    u=set().union(*req[s:t+1]); pages=trace['pages']
    if any((not ignore_birth and pages[p]['first']>s) or
           (not ignore_death and pages[p]['last']<t) for p in u):return None
    w=sum(pages[p]['weight'] for p in u)
    return trace['setup']+(1+trace['visit_weight']*(t-s+1))*w,u


def solve(trace:dict[str,Any], *,mode:str='fast')->dict[str,Any]:
    req=requirements(trace);pages=trace['pages'];n=len(req);P=len(pages)
    dp=[0];parent=[];frontier=[];ops=0
    if mode=='fast' and trace['visit_weight']==0:
        bound=n*(trace['setup']+sum(p['weight'] for p in pages))+1
        tree=RangeMin(n,4*bound);last=[-1]*P;expiry=[[] for _ in range(n)]
        for p,x in enumerate(pages):
            if x['last']+1<n:expiry[x['last']+1].append(p)
        lower=0
        for t,need in enumerate(req):
            lower=max([lower]+[last[p]+1 for p in expiry[t]]+[pages[p]['first'] for p in need])
            tree.set(t,dp[t]+trace['setup']);ops+=1
            for p in sorted(need):
                tree.add(last[p]+1,t,pages[p]['weight']);last[p]=t;ops+=1
            best,s=tree.min(lower,t);ops+=1
            dp.append(best);parent.append(s);frontier.append(lower)
    else:
        for t in range(n):
            options=[]
            for s in range(t+1):
                z=span(trace,req,s,t,ignore_birth=mode=='no_birth',ignore_death=mode=='no_death');ops+=1
                if z is not None:options.append((dp[s]+z[0],s))
            v,s=min(options);dp.append(v);parent.append(s)
    intervals=[];t=n
    while t:
        s=parent[t-1];intervals.append([s,t-1]);t=s
    intervals.reverse()
    cert=_make_certificate_from_requirements(trace,intervals,dp,req)
    return {'certificate':cert,'producer_metrics':{'operations':ops,'frontier':frontier,
             'algorithm':'last-use-range-min' if mode=='fast' and trace['visit_weight']==0 else 'direct-dynamic-program'}}


def make_certificate(trace:dict[str,Any],intervals:list[list[int]],potentials:list[int])->dict[str,Any]:
    return _make_certificate_from_requirements(trace,intervals,potentials,requirements(trace))


def _make_certificate_from_requirements(trace:dict[str,Any],intervals:list[list[int]],
                                        potentials:list[int],req:list[set[int]])->dict[str,Any]:
    epochs=[];total=0
    for s,t in intervals:
        U=set().union(*req[s:t+1]);descriptors=[]
        for p in sorted(U):
            x=trace['pages'][p]
            descriptors.append([p,x['slot'],x['generation'],x['content'],x['format'],x['kv_group']])
        c=trace['setup']+(1+trace['visit_weight']*(t-s+1))*sum(trace['pages'][p]['weight'] for p in U)
        total+=c;epochs.append({'start':s,'end':t,'pages':descriptors,'cost':c})
    return {'epochs':epochs,'potentials':potentials,
            'frontiers':[s['frontier'] for s in trace['steps']],'total_cost':total}


def baseline(trace:dict[str,Any],kind:str)->dict[str,Any]:
    req=requirements(trace);n=len(req);cuts=[];s=0
    if kind=='single':cuts=[[0,n-1]]
    elif kind=='fresh':cuts=[[t,t] for t in range(n)]
    elif kind in ('greedy','periodic'):
        while s<n:
            end=s
            cap=n-1 if kind=='greedy' else min(n-1,((s//4)+1)*4-1)
            while end<cap and span(trace,req,s,end+1) is not None:end+=1
            cuts.append([s,end]);s=end+1
    else:raise ValueError('unknown baseline')
    valid=all(span(trace,req,s,t) is not None for s,t in cuts)
    c=_make_certificate_from_requirements(trace,cuts,[0]*(n+1),req)
    visits=sum((e['end']-e['start']+1)*len(e['pages']) for e in c['epochs'])
    return {'cost':c['total_cost'],'epochs':len(cuts),'page_visits':visits,'valid':valid,'cuts':cuts}


def main()->None:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('trace',type=Path);ap.add_argument('output',type=Path)
    ns=ap.parse_args()
    try:
        with ns.trace.open("rb") as source:
            raw=source.read(4*1024**2+1)
        if len(raw)>4*1024**2:raise ValueError('trace exceeds 4 MiB')
        cert=solve(json.loads(raw))['certificate']
        ns.output.write_text(json.dumps(cert,sort_keys=True,separators=(',',':'))+'\n',encoding='utf-8')
    except (ValueError,KeyError,IndexError,TypeError,OSError) as e:
        ap.exit(2,f'producer: {e}\n')
if __name__=='__main__':main()
