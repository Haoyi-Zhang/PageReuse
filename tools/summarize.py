#!/usr/bin/env python3
"""Summarize retained results only; never invokes a solver, checker or oracle."""
from __future__ import annotations
import argparse, csv, json, statistics
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def records(path: Path)->list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
def save(path: Path, rows: list[dict])->None:
    if not rows: raise ValueError('empty table: '+str(path))
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def components(trace: dict, cert: dict)->tuple[int,int,int]:
    c0=v=visits=0
    for epoch in cert['epochs']:
        weight=sum(trace['pages'][d[0]]['weight'] for d in epoch['pages'])
        length=epoch['end']-epoch['start']+1
        c0+=trace['setup']+weight;v+=length*weight;visits+=length*len(epoch['pages'])
    return c0,v,visits

def main()->None:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--campaign',type=Path,default=ROOT/'results/campaign',help='campaign result directory to summarize')
    ap.add_argument('--out',type=Path,default=ROOT/'results/tables')
    ns=ap.parse_args()
    ns.out.mkdir(parents=True,exist_ok=True)
    raw=ns.campaign
    pos=records(raw/'positive.jsonl')
    traces={r['id']:r['trace'] for r in records(ROOT/'inputs/traces.jsonl')}
    certs={r['id']:r['certificate'] for r in records(raw/'certificates.jsonl')}
    groups=[('Tiny controls',pos[:48]),('Short including tight family',pos[48:160]),('Medium',pos[160:184]),('Large',pos[184:196]),('Boundary',pos[196:200])]
    coverage=[]
    for label,rows in groups:
        coverage.append(dict(stratum=label,cases=len(rows),steps_min=min(r['steps'] for r in rows),steps_max=max(r['steps'] for r in rows),pages_min=min(r['pages'] for r in rows),pages_max=max(r['pages'] for r in rows),max_edges=max(r['edges'] for r in rows),max_certificate_bytes=max(r['certificate_bytes'] for r in rows),median_producer_us=statistics.median(r['producer_ns'] for r in rows)/1000,median_checker_us=statistics.median(r['checker_ns'] for r in rows)/1000))
    save(ns.out/'coverage.csv',coverage)
    base=[]
    for name in ('fresh','greedy','periodic','single'):
        eligible=[r for r in pos if name in (r['baselines'] or {})]
        valid=[r for r in eligible if r['baselines'][name]['valid']]
        ratios=[r['baselines'][name]['cost']/r['opt'] for r in valid if r['opt']>0]
        base.append(dict(policy=name,parents=len(eligible),valid=len(valid),invalid=len(eligible)-len(valid),strictly_worse=sum(r['baselines'][name]['cost']>r['opt'] for r in valid),zero_opt_valid=sum(r['opt']==0 for r in valid),ratio_n=len(ratios),max_ratio=max(ratios),sum_valid_cost=sum(r['baselines'][name]['cost'] for r in valid),sum_paired_opt=sum(r['opt'] for r in valid)))
    save(ns.out/'baselines.csv',base)
    mut=records(raw/'mutations.jsonl');counts=Counter((r['kind'],r['result']['code']) for r in mut)
    save(ns.out/'mutations.csv',[dict(family=k,verdict=code,cases=n,rejected=sum(not r['result']['accepted'] for r in mut if r['kind']==k),safety_only_accepts=sum(bool(r['safety_only'] and r['safety_only']['accepted']) for r in mut if r['kind']==k)) for (k,code),n in sorted(counts.items())])
    tight=[]
    for r in pos[48:56]:
        m=traces[r['id']]['pages'][1]['weight'];g=r['baselines']['greedy']['cost']
        tight.append(dict(id=r['id'],weight=m,optimal=r['opt'],greedy=g,ratio=g/r['opt']))
    save(ns.out/'tight.csv',tight)
    sensitivity=records(raw/'sensitivity.jsonl');parents=sorted({r['parent'] for r in sensitivity});sr=[]
    for parent in parents:
        c0,v,u=components(traces[parent],certs[parent]);sr.append(dict(parent=parent,rho=0,publication=c0,weighted_visits=v,page_visits=u,objective=certs[parent]['total_cost']))
    for r in sensitivity:
        c0,v,u=components(r['trace'],r['certificate']);sr.append(dict(parent=r['parent'],rho=r['rho'],publication=c0,weighted_visits=v,page_visits=u,objective=r['certificate']['total_cost']))
    save(ns.out/'sensitivity_pairs.csv',sorted(sr,key=lambda r:(r['parent'],r['rho'])))
    sa=[]
    for rho in sorted({r['rho'] for r in sr}):
        rows=[r for r in sr if r['rho']==rho]
        sa.append(dict(rho=rho,parents=len(rows),publication=sum(r['publication'] for r in rows),weighted_visits=sum(r['weighted_visits'] for r in rows),page_visits=sum(r['page_visits'] for r in rows),objective=sum(r['objective'] for r in rows)))
    save(ns.out/'sensitivity.csv',sa)
    ab=records(raw/'ablations.jsonl')
    save(ns.out/'ablations.csv',[dict(mode=mode,parents=sum(r['mode']==mode for r in ab),accepted=sum(r['mode']==mode and r['result']['accepted'] for r in ab),lifetime_rejects=sum(r['mode']==mode and r['result']['code']=='lifetime' for r in ab)) for mode in ('no_birth','no_death')])
    inventory={'positive':len(pos),'oracle':sum(r['oracle'] is not None for r in pos),'mutations':len(mut),'sensitivity':len(sensitivity),'ablations':len(ab),'max_certificate_bytes':max(r['certificate_bytes'] for r in pos),'min_certificate_bytes':min(r['certificate_bytes'] for r in pos),'max_actual_edges':max(r['edges'] for r in pos),'total_steps':sum(r['steps'] for r in pos),'positive_checker_intervals':sum(r['span_obligations'] for r in pos),'zero_opt_ids':[r['id'] for r in pos if not r['opt']],'notes':'Arithmetic and aggregation of saved records only; no new optimization or validation execution.'}
    (ns.out/'inventory.json').write_text(json.dumps(inventory,indent=2)+'\n')
    print(json.dumps(inventory,sort_keys=True))
if __name__=='__main__':main()
