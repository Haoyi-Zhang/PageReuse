"""Deterministic, synthetic finite traces. No model outputs or serving measurements."""
from __future__ import annotations
import argparse,json,random
from pathlib import Path


def typed(needs,lives,weights,setup=1,*,heads=4,alias=False,cycle=False,recycle=False):
    T=len(needs);P=len(lives);pages=[];ends={};gens={}
    # Interval coloring permits deliberate slot reuse while prohibiting overlap.
    order=sorted(range(P),key=lambda p:(lives[p][0],p));slots={}
    for p in order:
        a,b=lives[p]
        free=[s for s,e in ends.items() if e<a] if recycle else []
        s=min(free) if free else len(ends)
        gens[s]=gens.get(s,0)+1;ends[s]=b;slots[p]=(s,gens[s])
    for p,(a,b) in enumerate(lives):
        s,g=slots[p]
        pages.append(dict(slot=s,generation=g,content=1000+p,format='fp16' if p%2==0 else 'int8',
                          kv_group=p%min(heads,8),first=a,last=b,base=0,length=4,weight=weights[p]))
    steps=[]
    for t,R in enumerate(needs):
        bind=[];atoms=[]
        for p in sorted(R):
            x=pages[p];h=p%heads
            bind.append([h,p,p,x['content'],x['format'],x['kv_group']]);atoms.append([h,p,0,1+(t%3)])
        if alias and R:
            p=min(R);x=pages[p];h=(p%heads+1)%heads
            # Same logical page index under another head denotes the exact same immutable incarnation.
            if [h,p] not in [b[:2] for b in bind]:
                bind.append([h,p,p,x['content'],x['format'],x['kv_group']]);atoms.append([h,p,0,1])
        if cycle:
            nodes=[{'children':[1],'atoms':atoms},{'children':[0],'atoms':[]}]
        else:nodes=[{'children':[],'atoms':atoms}]
        steps.append(dict(frontier=2,bindings=bind,nodes=nodes,roots=[0]))
    return dict(pages=pages,steps=steps,setup=setup,visit_weight=0,page_size=4,address_bits=16,heads=heads)


def random_case(seed,T,P,kind):
    r=random.Random(seed);lives=[]
    for p in range(P):
        if kind=='stable':a,b=0,T-1
        elif kind=='birth':a,b=(0 if p<max(1,P//4) else r.randrange(T)),T-1
        elif kind=='expiry':a,b=0,(T-1 if p<max(1,P//4) else r.randrange(T))
        elif kind=='recycle':
            q=max(1,T//4);a=min(T-1,(p%4)*q);b=T-1 if p%4==3 else min(T-1,a+q-1)
        else:
            a=r.randrange(T);b=r.randrange(a,T)
        lives.append((a,b))
    needs=[]
    for t in range(T):
        active=[p for p,(a,b) in enumerate(lives) if a<=t<=b]
        k=min(len(active),16 if T==64 else max(1,P//3))
        needs.append(set(r.sample(active,k)) if active and (kind!='empty' or t%3) else set())
    weights=[r.choice([1,2,4,16,64]) for _ in lives]
    return typed(needs,lives,weights,setup=[0,1,7,32][seed%4],heads=32 if T==64 else 4,
                 alias=T<64 and seed%2==0,cycle=seed%3==0,recycle=kind=='recycle')


def corpus():
    rows=[]
    def add(trace,stratum,seed=None):rows.append(dict(id=f'case-{len(rows):03d}',stratum=stratum,seed=seed,trace=trace))
    # This null example excludes a tempting but invalid batching improvement: page 2 is born too late.
    add(typed([{0},{1},{1,2}],[(0,1),(0,2),(2,2)],[1,1024,1]),'tiny-birth-boundary')
    # A genuine maximal-reuse counterexample; no late-born third page is present.
    add(typed([{0},{1},{1}],[(0,1),(0,2)],[1,1024]),'tiny-greedy-gap')
    add(typed([{0},{0},{0}],[(0,2),(0,0)],[2,1]),'tiny-unused-expiry')
    add(typed([set(),{0},set(),{0}],[(0,3)],[1],0),'tiny-empty-zero-setup')
    add(typed([{0},{1},{0},{1}],[(0,3),(0,3)],[2,3],1,alias=True,cycle=True),'tiny-alias-cycle')
    add(typed([{0},{0},{1},{1}],[(0,1),(2,3)],[2,2],1,recycle=True),'tiny-recycled-slot')
    for i in range(42):
        seed=104842+i;kind=['stable','birth','expiry','mixed','recycle','empty'][i%6]
        add(random_case(seed,3+i%3,2+i%3,kind),'tiny-'+kind,seed)
    for i in range(8):
        M=[1,2,4,16,64,256,1024,65536][i]
        add(typed([{0},{1},{1}],[(0,1),(0,2)],[1,M]),'greedy-tight-family')
    for i in range(104):
        seed=204842+i;kind=['stable','birth','expiry','mixed','recycle','empty'][i%6]
        add(random_case(seed,5+i%4,6+i%11,kind),'regular-'+kind,seed)
    for i in range(24):
        seed=304842+i;kind=['stable','birth','expiry','mixed','recycle','empty'][i%6]
        add(random_case(seed,16,32,kind),'medium-'+kind,seed)
    for i in range(12):
        seed=404842+i;kind=['stable','birth','expiry','mixed','recycle','empty'][i%6]
        add(random_case(seed,32,64,kind),'large-'+kind,seed)
    for i,kind in enumerate(['stable','birth','expiry','recycle']):
        add(random_case(504842+i,64,256,kind),'boundary-'+kind,504842+i)
    assert len(rows)==200
    return rows


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('output',type=Path);a=ap.parse_args()
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(''.join(json.dumps(x,sort_keys=True,separators=(',',':'))+'\n' for x in corpus()))
if __name__=='__main__':main()
