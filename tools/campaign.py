"""Reproduce bounded finite certificate checks from retained, original inputs.

Run from any working directory. No network, third-party packages, or paper files
are used. Results are flushed after each case; an interrupted run is never PASS.
"""
from __future__ import annotations
import argparse, copy, json, os, resource, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests'),str(ROOT/'tools')]
import producer, checker
from oracle import analyze
from generate import corpus


def write_json(path, obj):
    path.write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n',encoding='utf-8')


class Budget:
    def __init__(self, cap):
        self.cap=cap; self.used=0; self.categories={}
    def charge(self,n,kind):
        if self.used+n>self.cap:
            raise RuntimeError(f'obligation budget: {self.used}+{n}>{self.cap}')
        self.used+=n; self.categories[kind]=self.categories.get(kind,0)+n
    def room(self,n):
        if self.used+n>self.cap:
            raise RuntimeError(f'preflight reserve: {self.used}+{n}>{self.cap}')


def recost(trace,cert):
    total=0
    for ep in cert['epochs']:
        ep['cost']=trace['setup']+(1+trace['visit_weight']*(ep['end']-ep['start']+1))*sum(trace['pages'][d[0]]['weight'] for d in ep['pages'])
        total+=ep['cost']
    cert['total_cost']=total


def mutation(row, cert, kind, budget):
    tr=copy.deepcopy(row['trace']);c=copy.deepcopy(cert);T=len(tr['steps'])
    first=next(((j,0) for j,e in enumerate(c['epochs']) if e['pages']),None)
    if kind=='omission':
        if first is None:return None
        j,k=first;c['epochs'][j]['pages'].pop(k);recost(tr,c)
    elif kind=='stale-generation':
        if first is None:return None
        j,k=first;c['epochs'][j]['pages'][k][2]+=1
    elif kind=='alias-identity':
        st=next((s for s in tr['steps'] if s['bindings']),None)
        if st is None:return None
        st['bindings'][0][3]+=1
    elif kind=='causal-frontier':
        if first is None:return None
        c['frontiers'][c['epochs'][first[0]]['start']]+=1
    elif kind=='arithmetic':c['epochs'][0]['cost']+=1;c['total_cost']+=1
    elif kind=='lower-bound':
        bound=T*(tr['setup']+sum(p['weight'] for p in tr['pages']))
        if c['potentials'][-1]>=bound:return None
        c['potentials'][-1]+=1
    elif kind=='lifetime':
        # A single evaluated interval, without invoking a baseline's search.
        req=producer.requirements(tr);budget.charge(1,'mutation_eligibility')
        u=set().union(*req)
        if all(tr['pages'][p]['first']==0 and tr['pages'][p]['last']==T-1 for p in u):return None
        c=producer.make_certificate(tr,[[0,T-1]],c['potentials'])
    elif kind=='suboptimal':
        # Direct singleton partition: each evaluated singleton is counted.
        budget.charge(T,'mutation_eligibility')
        f=producer.make_certificate(tr,[[t,t] for t in range(T)],c['potentials'])
        if f['total_cost']<=c['total_cost']:return None
        c=f
    else:raise ValueError(kind)
    return tr,c


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--budget',type=int,default=34018,help='hard obligation cap for this invocation')
    a=ap.parse_args()
    if not 1<=a.budget<=34018:ap.error('budget must be in 1..34018')
    a.out.mkdir(parents=True,exist_ok=True)
    if any(a.out.iterdir()):ap.error('output directory must be empty; existing evidence is never overwritten')
    if hasattr(os,'sched_setaffinity'):os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
    resource.setrlimit(resource.RLIMIT_AS,(2500*1024**2,2500*1024**2))
    resource.setrlimit(resource.RLIMIT_CPU,(90,90))
    start=time.perf_counter();cpu=time.process_time();b=Budget(a.budget)
    rows=[json.loads(s) for s in (ROOT/'inputs/traces.jsonl').read_text().splitlines()]
    assert rows==corpus(),'retained input differs from deterministic construction'
    files={k:(a.out/(k+'.jsonl')).open('w',encoding='utf-8') for k in ['positive','certificates','mutations','sensitivity','ablations']}
    def save(k,row):
        files[k].write(json.dumps(row,sort_keys=True,separators=(',',':'))+'\n');files[k].flush()
    original_span=producer.span
    def counted_span(*args,**kwargs):
        b.charge(1,'producer_candidate_intervals');return original_span(*args,**kwargs)
    producer.span=counted_span
    def solve(tr,mode='fast'):
        T=len(tr['steps']);W=T*(T+1)//2
        b.room(T if mode=='fast' and tr['visit_weight']==0 else W)
        z=producer.solve(tr,mode=mode)
        if mode=='fast' and tr['visit_weight']==0:b.charge(T,'producer_minimum_queries')
        return z
    def check(tr,c,optimal=True):
        T=len(tr['steps']);b.room(1+(T*(T+1)//2 if optimal else 0))
        v=checker.check(tr,c,optimal=optimal)
        b.charge(1,'certificate_replays');b.charge(v['span_obligations'],'checker_intervals')
        return v
    certs=[];success=[];mutants=[];sens=[];abl=[]
    try:
        for i,row in enumerate(rows):
            tr=row['trace'];t=time.perf_counter_ns();z=solve(tr);prod_ns=time.perf_counter_ns()-t
            c=z['certificate'];t=time.perf_counter_ns();v=check(tr,c);check_ns=time.perf_counter_ns()-t
            assert v['accepted'],(row['id'],v)
            if i<48:
                T=len(tr['steps']);P=len(tr['pages']);b.room(T*(T+1)//2*2**P+2**(T-1))
                oracle=analyze(tr);b.charge(oracle['obligations'],'exhaustive_choices')
                assert oracle['cost']==c['total_cost'],(row['id'],oracle,c)
            else:oracle=None
            # Budget repair fixes this diagnostic subset by identifier, not outcome.
            bs={k:producer.baseline(tr,k) for k in ['fresh','greedy','periodic','single']} if i<56 else None
            if bs:
                assert all(bs[k]['cost']>=c['total_cost'] for k in ['fresh','greedy','periodic'])
                assert bs['greedy']['cost']<=2*c['total_cost']-tr['setup']*v['epochs']
            out=dict(id=row['id'],stratum=row['stratum'],steps=len(tr['steps']),pages=len(tr['pages']),
                edges=v['dependency_edges'],opt=c['total_cost'],epochs=v['epochs'],descriptors=v['descriptors'],page_visits=v['page_visits'],
                producer_ns=prod_ns,checker_ns=check_ns,certificate_bytes=len(json.dumps(c,sort_keys=True,separators=(',',':')).encode()),
                operations=z['producer_metrics']['operations'],span_obligations=v['span_obligations'],oracle=oracle,baselines=bs)
            success.append(out);certs.append(dict(id=row['id'],certificate=c));save('positive',out);save('certificates',certs[-1])
            if (i+1)%25==0:
                write_json(a.out/'progress.json',dict(completed=i+1,obligations=b.used,cpu_s=time.process_time()-cpu,status='in_progress'))
                print(f'positive {i+1}/{len(rows)}; obligations={b.used}',flush=True)
        for kind in ['omission','stale-generation','alias-identity','causal-frontier','arithmetic','lower-bound','lifetime','suboptimal']:
            count=0
            for row,zz in zip(rows,certs):
                pair=mutation(row,zz['certificate'],kind,b)
                if pair is None:continue
                tr,c=pair;v=check(tr,c);assert not v['accepted'],('missed mutation',kind,row['id'])
                sa=check(tr,c,optimal=False) if kind=='suboptimal' else None
                if sa is not None:assert sa['accepted'],sa
                out=dict(id=f'mutation-{len(mutants):03d}',parent=row['id'],kind=kind,trace=tr,certificate=c,result=v,safety_only=sa)
                mutants.append(out);save('mutations',out);count+=1
                if count==50:break
            assert count==50,('mutation eligibility shortage',kind,count)
        stable=[r for r in rows if r['stratum']=='regular-stable'][:8]
        for row in stable:
            for rho in [1,4,16,64]:
                tr=copy.deepcopy(row['trace']);tr['visit_weight']=rho;z=solve(tr);v=check(tr,z['certificate']);assert v['accepted'],v
                out=dict(id=f'sensitivity-{len(sens):03d}',parent=row['id'],rho=rho,trace=tr,certificate=z['certificate'],result=v)
                sens.append(out);save('sensitivity',out)
        # Fixed prefix of eight positive cases, chosen before this repaired run.
        for row in rows[:8]:
            for mode in ['no_birth','no_death']:
                z=solve(row['trace'],mode);v=check(row['trace'],z['certificate'])
                out=dict(id=row['id'],mode=mode,cost=z['certificate']['total_cost'],certificate=z['certificate'],result=v)
                abl.append(out);save('ablations',out)
        summary=dict(positive_cases=len(success),mutation_cases=len(mutants),sensitivity_cases=len(sens),
            generated_campaign_cases=len(success)+len(mutants)+len(sens),oracle_cases=48,baseline_cases=56,ablation_parent_cases=8,
            ablation_certificates=len(abl),obligations=b.used,obligation_categories=b.categories,cpu_s=time.process_time()-cpu,
            wall_s=time.perf_counter()-start,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,workers=1,
            status='finite_campaign_passed',public_runtime_traces=0,baseline_scope='first 56 identifiers',ablation_scope='first 8 identifiers')
        write_json(a.out/'summary.json',summary)
        (a.out/'progress.json').unlink(missing_ok=True)
        print(json.dumps(summary,indent=2))
    except BaseException as exc:
        write_json(a.out/'progress.json',dict(completed=len(success),mutations=len(mutants),sensitivity=len(sens),
            obligations=b.used,cpu_s=time.process_time()-cpu,status='incomplete',failure=type(exc).__name__))
        raise
    finally:
        producer.span=original_span
        for f in files.values():f.close()
if __name__=='__main__':main()
