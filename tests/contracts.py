"""Fixed defensive schema checks and a cut-formulation cross-check.

Only original local data are used. This is not an exploit test or a formal proof.
The scope is fixed before execution: the first eight trace identifiers for all
cut masks, plus the named contract examples below. No full campaign is rerun.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('isolated_checker',ROOT/'src/checker.py')
checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args()
    if args.out.exists() and any(args.out.iterdir()):raise SystemExit('output must be new or empty')
    args.out.mkdir(parents=True,exist_ok=True)
    resource.setrlimit(resource.RLIMIT_AS,(2500*1024**2,2500*1024**2))
    resource.setrlimit(resource.RLIMIT_CPU,(90,90))
    if hasattr(os,'sched_setaffinity'):os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
    start=time.process_time();wall=time.monotonic()
    rows=[json.loads(x) for x in (ROOT/'inputs/traces.jsonl').read_text().splitlines()]
    traces={x['id']:x['trace'] for x in rows}
    certs={x['id']:x['certificate'] for x in map(json.loads,(ROOT/'results/campaign/certificates.jsonl').read_text().splitlines())}
    results=[];obligations=0;cut_choices=0;cut_intervals=0
    def charge(n):
        nonlocal obligations
        if obligations+n>500:raise AssertionError('contract-test obligation cap')
        obligations+=n
    def test(name,trace,cert,accept,code=None,optimal=True):
        # Preflight the complete direct interval loop, even for early rejection.
        n=len(trace.get('steps',[])) if isinstance(trace,dict) else 0
        if obligations+1+n*(n+1)//2>500:raise AssertionError('checker preflight')
        ans=checker.check(trace,cert,optimal=optimal)
        charge(ans['certificate_obligations']+ans['span_obligations'])
        results.append({'name':name,'expected_accept':accept,'expected_code':code,'result':ans})
        assert ans['accepted']==accept,(name,ans)
        if code is not None:assert ans['code']==code,(name,ans)
    def altered_trace(name,change,code,parent='case-002'):
        tr=deepcopy(traces[parent]);change(tr)
        test(name,tr,certs[parent],False,code)
    def altered_cert(name,change,code,parent='case-002'):
        ce=deepcopy(certs[parent]);change(ce)
        test(name,traces[parent],ce,False,code)
    test('ordinary-valid',traces['case-002'],certs['case-002'],True)
    test('alias-cycle-valid',traces['case-004'],certs['case-004'],True)
    test('recycled-slot-valid',traces['case-005'],certs['case-005'],True)
    altered_trace('boolean-is-not-integer',lambda t:t.update(setup=True),'integer')
    altered_trace('zero-page-weight',lambda t:t['pages'][0].update(weight=0),'integer')
    altered_trace('address-overflow',lambda t:t.update(address_bits=3),'address')
    altered_trace('unknown-top-level-field',lambda t:t.update(extra=1),'fields')
    altered_trace('empty-time-domain',lambda t:t.update(steps=[]),'empty_model')
    altered_trace('duplicate-logical-binding',lambda t:t['steps'][0]['bindings'].append(t['steps'][0]['bindings'][0]),'duplicate_binding')
    altered_trace('missing-logical-binding',lambda t:t['steps'][0].update(bindings=[]),'missing_binding')
    altered_trace('invalid-root',lambda t:t['steps'][0].update(roots=[999]),'integer')
    altered_trace('uninitialized-lane',lambda t:t['steps'][0]['nodes'][0]['atoms'][0].__setitem__(3,5),'integer')
    altered_trace('future-required-lane',lambda t:t['steps'][0]['nodes'][0]['atoms'][0].__setitem__(3,4),'causal_dependency')
    altered_trace('overlapping-slot-lifetimes',lambda t:t['pages'][1].update(first=1),'physical_alias','case-005')
    altered_trace('nonincreasing-generation',lambda t:t['pages'][1].update(generation=1),'generation_order','case-005')
    def old_binding(t):t['steps'][2]['bindings'].append(deepcopy(t['steps'][0]['bindings'][0]))
    altered_trace('inactive-binding',old_binding,'inactive_binding','case-005')
    def too_many_edges(t):t['steps'][0]['nodes'][0]['atoms']*=2048
    altered_trace('aggregate-edge-limit',too_many_edges,'edge_bound')
    altered_cert('stale-descriptor-generation',lambda c:c['epochs'][0]['pages'][0].__setitem__(2,2),'descriptor_binding')
    altered_cert('wrong-descriptor-slot',lambda c:c['epochs'][0]['pages'][0].__setitem__(1,1),'descriptor_binding')
    altered_cert('duplicate-descriptor',lambda c:c['epochs'][0]['pages'].append(c['epochs'][0]['pages'][0]),'descriptor_order')
    altered_cert('missing-coverage',lambda c:c['epochs'][0].update(pages=[]),'coverage')
    altered_cert('partition-gap',lambda c:c['epochs'][0].update(start=1),'partition')
    altered_cert('incorrect-epoch-cost',lambda c:c['epochs'][0].update(cost=4),'epoch_cost')
    altered_cert('incorrect-mask-copy',lambda c:c['frontiers'].__setitem__(0,3),'causal_frontier')
    altered_cert('raised-prefix-bound',lambda c:c['potentials'].__setitem__(1,4),'dual_inequality')
    altered_cert('primal-dual-gap',lambda c:c['potentials'].__setitem__(-1,0),'primal_dual_gap')
    tr=deepcopy(traces['case-002']);tr['steps'][0]['nodes'].append({'children':[],'atoms':[[0,0,0,4]]})
    test('unreachable-future-atom-is-not-required',tr,certs['case-002'],True)
    tr=deepcopy(traces['case-002']);tr['address_bits']=4
    test('address-end-equals-space-bound',tr,certs['case-002'],True)

    with tempfile.TemporaryDirectory() as td:
        td=Path(td)
        for name,raw,code in [('duplicate-json-key','{"x":1,"x":2}','duplicate_key'),
                              ('nonfinite-json','{"x":NaN}','nonfinite')]:
            path=td/'malformed.json';path.write_text(raw);charge(1)
            try:checker.load(path)
            except checker.Invalid as e:assert e.code==code;results.append({'name':name,'rejected':code})
            else:raise AssertionError(name)
        path=td/'oversized.json'
        with path.open('wb') as f:
            for _ in range(1025):f.write(b' '*4096)
        charge(1)
        try:checker.load(path)
        except checker.Invalid as e:assert e.code=='input_bytes';results.append({'name':'bounded-file-read','rejected':e.code})
        else:raise AssertionError('file byte limit')
        tracefile=td/'trace.json';certfile=td/'certificate.json'
        tracefile.write_text(json.dumps(traces['case-002']))
        proc=subprocess.run([sys.executable,str(ROOT/'src/producer.py'),str(tracefile),str(certfile)],capture_output=True,text=True,timeout=10)
        charge(len(traces['case-002']['steps']))
        assert proc.returncode==0,(proc.stdout,proc.stderr)
        results.append({'name':'producer-cli','exit_code':proc.returncode})
        for name,bad,expected in [('checker-cli',False,0),('checker-cli-rejection',True,2)]:
            if bad:
                ce=json.loads(certfile.read_text());ce['epochs'][0]['pages'][0][2]+=1;certfile.write_text(json.dumps(ce))
            proc=subprocess.run([sys.executable,str(ROOT/'src/checker.py'),str(tracefile),str(certfile)],capture_output=True,text=True,timeout=10)
            ans=json.loads(proc.stdout);charge(ans['certificate_obligations']+ans['span_obligations'])
            assert proc.returncode==expected,(name,proc.stdout,proc.stderr)
            results.append({'name':name,'exit_code':proc.returncode,'result':ans})

    # Independent cut characterization. It never calls producer.span/solve or
    # the checker normalizer. Full masks are retained, not a favorable sample.
    cut_rows=[]
    for row in rows[:8]:
        tr=row['trace'];T=len(tr['steps']);pages=tr['pages'];requirements=[]
        for st in tr['steps']:
            reached=set(st['roots'])
            while True:
                expanded=reached|{j for i in reached for j in st['nodes'][i]['children']}
                if expanded==reached:break
                reached=expanded
            bindings={(b[0],b[1]):b[2] for b in st['bindings']}
            requirements.append({bindings[a[0],a[1]] for i in reached for a in st['nodes'][i]['atoms']})
        occ={p:[t for t,R in enumerate(requirements) if p in R] for p in range(len(pages))}
        for mask in range(1<<(T-1)):
            charge(1);cut_choices+=1
            X={i for i in range(T-1) if mask>>i&1};cuts=sorted(X)+[T-1]
            s=0;direct_cost=0;direct_valid=True
            for e in cuts:
                charge(1);cut_intervals+=1
                U=set().union(*requirements[s:e+1]);direct_cost+=tr['setup']+sum(pages[p]['weight'] for p in U)
                direct_valid &= all(pages[p]['first']<=s and e<=pages[p]['last'] for p in U)
                s=e+1
            cut_valid=True;cut_cost=tr['setup']*(1+len(X))
            for p,times in occ.items():
                if not times:continue
                meta=pages[p];a,b=meta['first'],meta['last'];f,l=times[0],times[-1]
                if a>0:cut_valid &= any(a-1<=x<=f-1 for x in X)
                if b<T-1:cut_valid &= any(l<=x<=b for x in X)
                count=1+sum(any(left<=x<right for x in X) for left,right in zip(times,times[1:]))
                cut_cost+=meta['weight']*count
            assert (direct_valid,direct_cost)==(cut_valid,cut_cost),(row['id'],mask)
            cut_rows.append({'parent':row['id'],'cut_mask':mask,'valid':bool(direct_valid),'direct_cost':direct_cost,'cut_cost':cut_cost})
    (args.out/'contracts.json').write_text(json.dumps(results,indent=2,sort_keys=True)+'\n')
    (args.out/'cut-formulation.jsonl').write_text(''.join(json.dumps(x,sort_keys=True)+'\n' for x in cut_rows))
    usage=resource.getrusage(resource.RUSAGE_SELF);child=resource.getrusage(resource.RUSAGE_CHILDREN)
    summary={'status':'finite_contract_tests_passed','named_contract_tests':len(results),'cut_parent_cases':8,
             'cut_masks':cut_choices,'direct_cut_intervals':cut_intervals,'obligations':obligations,
             'cpu_self_s':time.process_time()-start,'cpu_children_s':child.ru_utime+child.ru_stime,
             'wall_s':time.monotonic()-wall,'peak_self_rss_kib':usage.ru_maxrss,'maximum_child_rss_kib':child.ru_maxrss,
             'aggregate_rss_upper_kib':usage.ru_maxrss+child.ru_maxrss,
             'parallel_children_max':1,'worker_cpu_affinity_count':1}
    (args.out/'summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    print(json.dumps(summary,sort_keys=True))
if __name__=='__main__':main()
