"""Independent, bounded checker for JSON page-selection certificates.

This file does not import the producer, its normalizer, its interval frontier,
its range tree, or any project helper. General theorems are pen-and-paper proofs;
this implementation is not a proof-assistant-verified checker.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Any


class Invalid(ValueError):
    def __init__(self, code: str, where: str):
        self.code=code; self.where=where
        super().__init__(f'{code}: {where}')


def need(ok:bool,code:str,where:str)->None:
    if not ok:raise Invalid(code,where)


def integer(x:Any,lo:int,hi:int,where:str)->None:
    need(type(x) is int and lo<=x<=hi,'integer',where)


def fields(obj:Any,keys:set[str],where:str)->None:
    need(type(obj) is dict and set(obj)==keys,'fields',where)


def array(x:Any,cap:int,where:str)->None:
    need(type(x) is list and len(x)<=cap,'array',where)


def load(path:Path)->Any:
    def unique(pairs):
        d={}
        for k,v in pairs:
            need(k not in d,'duplicate_key',str(k));d[k]=v
        return d
    with path.open("rb") as source:
        data=source.read(4*1024**2+1)
    need(len(data)<=4*1024**2,'input_bytes',path.name)
    return json.loads(data,object_pairs_hook=unique,
                      parse_constant=lambda x: (_ for _ in ()).throw(Invalid('nonfinite',x)))


def normalize(trace:Any)->tuple[list[set[int]],int]:
    fields(trace,{'pages','steps','setup','visit_weight','page_size','address_bits','heads'},'trace')
    integer(trace['setup'],0,2**20,'setup');integer(trace['visit_weight'],0,2**20,'visit_weight')
    integer(trace['page_size'],1,128,'page_size');integer(trace['address_bits'],1,64,'address_bits')
    integer(trace['heads'],1,32,'heads')
    array(trace['pages'],256,'pages');array(trace['steps'],64,'steps')
    P=len(trace['pages']);T=len(trace['steps']);need(P>=1 and T>=1,'empty_model','pages/steps')
    groups={};formats={'fp16':2,'int8':1};edge_count=0;node_count=0;binding_count=0
    for i,p in enumerate(trace['pages']):
        where=f'page {i}'
        fields(p,{'slot','generation','content','format','kv_group','first','last','base','length','weight'},where)
        integer(p['slot'],0,255,where+' slot');integer(p['generation'],1,2**31-1,where+' generation')
        integer(p['content'],0,2**31-1,where+' content');integer(p['kv_group'],0,31,where+' kv_group')
        integer(p['first'],0,T-1,where+' first');integer(p['last'],p['first'],T-1,where+' last')
        integer(p['base'],0,2**31-1,where+' base');integer(p['length'],1,trace['page_size'],where+' length')
        integer(p['weight'],1,2**20,where+' weight')
        need(type(p['format']) is str and p['format'] in formats,'layout',where)
        # The stride is fixed at the largest supported element width. This also
        # makes different slots physically disjoint for both supported layouts.
        end=p['slot']*trace['page_size']*2+p['length']*formats[p['format']]
        need(end<=2**trace['address_bits'],'address',where)
        groups.setdefault(p['slot'],[]).append((p['first'],p['last'],p['generation'],i))
    for slot in sorted(groups):
        epochs=sorted(groups[slot])
        for old,new in zip(epochs,epochs[1:]):
            need(old[1]<new[0],'physical_alias',f'slot {slot}, pages {old[3]},{new[3]}')
            need(old[2]<new[2],'generation_order',f'slot {slot}, pages {old[3]},{new[3]}')
    requirements=[]
    for t,st in enumerate(trace['steps']):
        loc=f'step {t}'
        fields(st,{'frontier','bindings','nodes','roots'},loc)
        integer(st['frontier'],0,2**31-1,loc+' frontier')
        array(st['bindings'],512,loc+' bindings');array(st['nodes'],2048,loc+' nodes');array(st['roots'],2048,loc+' roots')
        binding_count+=len(st['bindings']);node_count+=len(st['nodes'])
        need(binding_count<=8192 and node_count<=2048,'model_bound',loc)
        bindings={}
        for j,b in enumerate(st['bindings']):
            pos=f'{loc} binding {j}';array(b,6,pos);need(len(b)==6,'binding_shape',pos)
            h,l,p,c,f,g=b
            integer(h,0,trace['heads']-1,pos+' head');integer(l,0,255,pos+' logical')
            integer(p,0,P-1,pos+' page');integer(c,0,2**31-1,pos+' content');integer(g,0,31,pos+' group')
            need((h,l) not in bindings,'duplicate_binding',pos)
            meta=trace['pages'][p]
            need((c,f,g)==(meta['content'],meta['format'],meta['kv_group']),'alias_binding',pos)
            need(meta['first']<=t<=meta['last'],'inactive_binding',pos)
            bindings[h,l]=p
        nodes=st['nodes'];N=len(nodes)
        for r in st['roots']:integer(r,0,N-1,loc+' root')
        for j,node in enumerate(nodes):
            pos=f'{loc} node {j}';fields(node,{'children','atoms'},pos)
            array(node['children'],2048,pos+' children');array(node['atoms'],2048,pos+' atoms')
            edge_count+=len(node['children'])+len(node['atoms'])
            need(edge_count<=2048,'edge_bound',pos)
            for c in node['children']:integer(c,0,N-1,pos+' child')
            for k,a in enumerate(node['atoms']):
                at=f'{pos} atom {k}';array(a,4,at);need(len(a)==4,'atom_shape',at)
                h,l,lo,hi=a;integer(h,0,trace['heads']-1,at+' head');integer(l,0,255,at+' logical')
                need((h,l) in bindings,'missing_binding',at)
                integer(lo,0,trace['page_size']-1,at+' lower')
                integer(hi,lo+1,trace['pages'][bindings[h,l]]['length'],at+' upper')
        reachable=set();pending=list(st['roots'])
        while pending:
            j=pending.pop()
            if j in reachable:continue
            reachable.add(j);pending.extend(nodes[j]['children'])
        required=set()
        for j in sorted(reachable):
            for k,(h,l,lo,hi) in enumerate(nodes[j]['atoms']):
                p=bindings[h,l];meta=trace['pages'][p]
                cap=min(meta['length'],max(0,st['frontier']-meta['base']+1))
                need(hi<=cap,'causal_dependency',f'{loc} node {j} atom {k}')
                required.add(p)
        requirements.append(required)
    return requirements,edge_count


def check(trace:Any,cert:Any,*,optimal:bool=True)->dict[str,Any]:
    counters={'certificate_obligations':1,'span_obligations':0,'dependency_edges':0}
    try:
        required,edges=normalize(trace);counters['dependency_edges']=edges
        fields(cert,{'epochs','potentials','frontiers','total_cost'},'certificate')
        T=len(required);P=len(trace['pages']);pages=trace['pages']
        array(cert['frontiers'],T,'frontiers');need(len(cert['frontiers'])==T,'frontier_length','certificate')
        for t,q in enumerate(cert['frontiers']):
            integer(q,0,2**31-1,f'frontier {t}')
            need(q==trace['steps'][t]['frontier'],'causal_frontier',f'step {t}')
        bound=T*(trace['setup']+(1+trace['visit_weight']*T)*sum(p['weight'] for p in pages))
        integer(cert['total_cost'],0,bound,'total_cost')
        array(cert['potentials'],T+1,'potentials');need(len(cert['potentials'])==T+1,'potential_length','certificate')
        for i,v in enumerate(cert['potentials']):integer(v,0,bound,f'potential {i}')
        d=cert['potentials'];need(d[0]==0,'potential_origin','prefix 0')
        array(cert['epochs'],T,'epochs');need(len(cert['epochs'])>=1,'empty_partition','certificate')
        start=0;total=0;visits=0;descriptors=0
        for j,ep in enumerate(cert['epochs']):
            loc=f'epoch {j}';fields(ep,{'start','end','pages','cost'},loc)
            integer(ep['start'],0,T-1,loc+' start');integer(ep['end'],ep['start'],T-1,loc+' end')
            need(ep['start']==start,'partition',loc);s=ep['start'];t=ep['end'];start=t+1
            array(ep['pages'],P,loc+' pages');selected=set();previous=-1
            for k,desc in enumerate(ep['pages']):
                pos=f'{loc} descriptor {k}';array(desc,6,pos);need(len(desc)==6,'descriptor_shape',pos)
                p=desc[0];integer(p,0,P-1,pos+' page')
                need(p>previous,'descriptor_order',pos);previous=p;meta=pages[p]
                for ix in [1,2,3,5]:integer(desc[ix],0,2**31-1,pos+f' field {ix}')
                need(desc==[p,meta['slot'],meta['generation'],meta['content'],meta['format'],meta['kv_group']],
                     'descriptor_binding',pos)
                need(meta['first']<=s and t<=meta['last'],'lifetime',pos)
                selected.add(p)
            union=set()
            for q in range(s,t+1):union.update(required[q])
            need(union<=selected,'coverage',loc)
            if optimal:need(union==selected,'nonminimal_epoch',loc)
            expected=trace['setup']+(1+trace['visit_weight']*(t-s+1))*sum(pages[p]['weight'] for p in selected)
            integer(ep['cost'],0,bound,loc+' cost');need(ep['cost']==expected,'epoch_cost',loc)
            total+=expected;visits+=(t-s+1)*len(selected);descriptors+=len(selected)
        need(start==T,'partition_end','certificate');need(total==cert['total_cost'],'total_cost','certificate')
        if optimal:
            # Independent semantic enumeration. It intentionally neither reads a
            # supplied frontier nor invokes the producer's last-use recurrence.
            for t in range(T):
                union=set();weight=0;first=0;last=T-1
                for s in range(t,-1,-1):
                    counters['span_obligations']+=1
                    for p in required[s]:
                        if p not in union:
                            union.add(p);weight+=pages[p]['weight']
                            first=max(first,pages[p]['first']);last=min(last,pages[p]['last'])
                    if first<=s and t<=last:
                        edge=trace['setup']+(1+trace['visit_weight']*(t-s+1))*weight
                        need(d[t+1]<=d[s]+edge,'dual_inequality',f'interval [{s},{t}]')
            need(d[T]==total,'primal_dual_gap','final prefix')
        return {'accepted':True,'code':'accepted','total_cost':total,'epochs':len(cert['epochs']),
                'descriptors':descriptors,'page_visits':visits,**counters}
    except Invalid as e:
        return {'accepted':False,'code':e.code,'witness':e.where,**counters}
    except (KeyError,TypeError,ValueError,IndexError,OverflowError,RecursionError) as e:
        return {'accepted':False,'code':'malformed','witness':type(e).__name__,**counters}


def main()->None:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('trace',type=Path);ap.add_argument('certificate',type=Path)
    ap.add_argument('--safety-only',action='store_true',help='Do not certify minimum cost.')
    ns=ap.parse_args()
    try:answer=check(load(ns.trace),load(ns.certificate),optimal=not ns.safety_only)
    except (Invalid,OSError,ValueError,RecursionError) as e:
        answer={'accepted':False,'code':'input_parse','witness':str(e)}
    print(json.dumps(answer,sort_keys=True))
    if not answer['accepted']:raise SystemExit(2)
if __name__=='__main__':main()
