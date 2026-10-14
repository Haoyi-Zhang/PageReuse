"""Source-separated audit of every matched full-path sample, including zeros."""
import argparse,gzip,hashlib,json,statistics
from pathlib import Path
from evidence import loads,require,same
import check_workflow as workflow
ROOT=Path(__file__).resolve().parents[1]
ARMS=('ordinary-exact','certified-incremental','certified-range-min','certified-direct-union')
PHASES=('acquisition','planning','serialization','publication','consumer','native','cleanup')
FIELDS={'id','arm','round','position','objective','checker','frequency','full','phases','input_bytes','published_bytes','published_utf8','actual_values','actual_loads','actual_bytes','publications','descriptor_copies','sink','arena_bytes','passed'}
SOURCES={'native/allocator.cpp','native/NativeBridge.cs','native/NativePolicies.cs','native/NativePolicyTests.cs','native/NativePolicyTiming.cs','native/NativeCompleteCost.cs','native/complete_cost.ps1','src/checker.py','src/producer.py','native/check_complete_cost.py','native/evidence.py'}
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest().upper()
def integer(n,lo=0):require(type(n) is int and n>=lo,'nonnegative integer, not Boolean')
def clock(c):
    require(type(c) is dict and set(c)=={'wall_ticks','process_cpu_100ns'},'exact clock fields')
    for v in c.values():integer(v)
def shape(r):
    require(type(r) is dict and set(r)==FIELDS,'complete cost sample fields')
    require(r['arm'] in ARMS and r['objective']=='rho0-publication' and r['checker']=='optimality' and r['passed'] is True,'same guarantee')
    for k in ('round','position','frequency','input_bytes','published_bytes','actual_loads','actual_bytes','publications','descriptor_copies','sink','arena_bytes'):integer(r[k],1 if k=='frequency' else 0)
    require(r['round']<8 and r['position']<4,'fixed schedule range')
    require(type(r['published_utf8']) is str,'literal publication bytes')
    clock(r['full']);require(type(r['phases']) is dict and set(r['phases'])==set(PHASES),'all full-path phases')
    for c in r['phases'].values():clock(c)
    for k in ('wall_ticks','process_cpu_100ns'):
        require(r['full'][k]>=sum(c[k] for c in r['phases'].values()),'nested phase clocks cannot exceed enclosing actual total')
def ratio(n,d):
    integer(n);integer(d);return n/d if d else None
def audit(directory):
    env=loads((directory/'environment.json').read_text());protocol=loads((directory/'protocol.json').read_text())
    require(env['project_id']=='P054' and env['protocol']=='same-contract-complete-cost' and env['authority_kind']=='explicit-user-resume' and env['historical_reserved_slot_claimed'] is False,'scoped renewed authority, not fabricated reservation')
    require(set(env['source_sha256'])==SOURCES,'all measured source bindings')
    for n,h in env['source_sha256'].items():require(digest(ROOT/n)==h,('source',n))
    require(set(env['record_sha256'])=={'samples.jsonl.gz','completion.json','protocol.json','ready.json'},'all raw record bindings')
    for n,h in env['record_sha256'].items():require(digest(directory/n)==h,('record',n))
    require(protocol['inputs']==207 and protocol['rounds']==8 and protocol['measured_calls']==6624 and same(protocol['arms'],list(ARMS)),'fixed protocol')
    require(env['affinity']==1 and env['zero_ticks_retained'] is True and env['all_samples_retained'] is True and env['forced_gc'] is False,'execution/retention protocol')
    frozen=ROOT/'results/exact-document-workflow/inputs.jsonl.gz'
    require(digest(frozen)==env['input_manifest']['frozen_inputs_sha256'].upper(),'same frozen inputs')
    inputs={r['id']:r for r in workflow.rows(frozen)};require(len(inputs)==207,'full retained population')
    require(len(env['input_manifest']['files'])==207,'prepared file inventory')
    expected={};values={};accounting={}
    for id_,r in inputs.items():
        require(digest_bytes(r['input_utf8'].encode())==env['input_manifest']['files'][id_+'.json'].upper(),'serialized source bytes')
        expected[id_]=workflow.producer.solve(r['trace'])['certificate'];values[id_]=workflow.semantic.mandatory_values(r['trace'])
        require(workflow.checker.check(r['trace'],expected[id_])['accepted'],'independent optimality for all frozen inputs')
        accounting[id_]=workflow.semantic.accounting(r['trace'],expected[id_])
    per={};zeros={a:{'wall':0,'cpu':0} for a in ARMS};phase_zero={a:{p:dict(wall=0,cpu=0) for p in PHASES} for a in ARMS};raw_count=0;frequency=None;input_bytes=0;publication_bytes={a:0 for a in ARMS}
    with gzip.open(directory/'samples.jsonl.gz','rt',encoding='utf-8') as f:
        for line in f:
            r=loads(line);shape(r);case=raw_count//32;rr=(raw_count%32)//4;pos=raw_count%4
            require(case<207 and r['id']==list(inputs)[case] and r['round']==rr and r['position']==pos and r['arm']==ARMS[(rr+pos)%4],'complete fixed input/order/arm schedule')
            id_=r['id'];arm=r['arm'];key=(id_,rr,arm);require(key not in per,'no duplicate samples');per[key]=r
            frequency=r['frequency'] if frequency is None else frequency;require(r['frequency']==frequency,'fixed clock frequency')
            publication=loads(r['published_utf8']);target=expected[id_]
            if arm=='ordinary-exact':target={k:v for k,v in target.items() if k!='potentials'}
            require(same(publication,target),'actual publication, optimum and earliest-start tie')
            require(same(r['actual_values'],values[id_]),'all actual native mandatory values')
            for n,v in accounting[id_].items():
                if n in r:require(same(r[n],v),('actual native accounting',n))
            require(r['input_bytes']==len(inputs[id_]['input_utf8'].encode()) and r['published_bytes']==len(r['published_utf8'].encode()),'actual serialized byte counts')
            zeros[arm]['wall']+=r['full']['wall_ticks']==0;zeros[arm]['cpu']+=r['full']['process_cpu_100ns']==0
            for p,c in r['phases'].items():phase_zero[arm][p]['wall']+=c['wall_ticks']==0;phase_zero[arm][p]['cpu']+=c['process_cpu_100ns']==0
            input_bytes+=r['input_bytes'];publication_bytes[arm]+=r['published_bytes'];raw_count+=1
    require(raw_count==6624 and len(per)==6624,'all actual complete samples')
    require(loads((directory/'completion.json').read_text())==dict(status='MEASURED',measured_calls=6624,warmup_native_calls=828,consumer_regressions=4),'actual completion counters')
    by_case={};by_arm={a:dict(sum_full_wall_seconds=0,sum_full_process_cpu_seconds=0,published_bytes=publication_bytes[a],case_median_wall_ratio_above_ordinary=0,case_median_wall_ratio_below_ordinary=0,case_median_wall_ratio_equal_ordinary=0,zero_denominator_cpu_pairs=0,zero_numerator_cpu_pairs=0) for a in ARMS}
    for id_ in inputs:
        by_case[id_]={}
        for a in ARMS:
            rows=[per[id_,r,a] for r in range(8)];ratios=[ratio(per[id_,r,a]['full']['wall_ticks'],per[id_,r,ARMS[0]]['full']['wall_ticks']) for r in range(8)]
            cpu_ratios=[ratio(per[id_,r,a]['full']['process_cpu_100ns'],per[id_,r,ARMS[0]]['full']['process_cpu_100ns']) for r in range(8)]
            valid=[q for q in ratios if q is not None];cpu_valid=[q for q in cpu_ratios if q is not None]
            med=statistics.median(valid) if valid else None
            by_case[id_][a]=dict(median_paired_full_wall_ratio=med,wall_pairs_defined=len(valid),median_defined_cpu_ratio=statistics.median(cpu_valid) if cpu_valid else None,cpu_pairs_defined=len(cpu_valid),sum_full_wall_ticks=sum(r['full']['wall_ticks'] for r in rows),sum_full_cpu_100ns=sum(r['full']['process_cpu_100ns'] for r in rows))
            b=by_arm[a];b['sum_full_wall_seconds']+=by_case[id_][a]['sum_full_wall_ticks']/frequency;b['sum_full_process_cpu_seconds']+=by_case[id_][a]['sum_full_cpu_100ns']/1e7
            b['zero_denominator_cpu_pairs']+=8-len(cpu_valid);b['zero_numerator_cpu_pairs']+=sum(per[id_,r,a]['full']['process_cpu_100ns']==0 for r in range(8))
            if med is not None:b['case_median_wall_ratio_'+('above' if med>1 else 'below' if med<1 else 'equal')+'_ordinary']+=1
    # Each phase total sums actual nested observations across those same calls.
    # It is NEVER substituted for the enclosing full-path observations.
    phases={a:{p:{'sum_wall_seconds':sum(r['phases'][p]['wall_ticks'] for (_,_,arm),r in per.items() if arm==a)/frequency,'sum_process_cpu_seconds':sum(r['phases'][p]['process_cpu_100ns'] for (_,_,arm),r in per.items() if arm==a)/1e7} for p in PHASES} for a in ARMS}
    return dict(status='COMPLETE_COST_RECORDS_PASSED',inputs=207,retained_inputs=200,separate_controls=7,measured_native_calls=raw_count,warmup_native_calls=828,rounds=8,frequency=frequency,serialized_input_bytes_acquired=input_bytes,arms=by_arm,phases=phases,zero_full_samples=zeros,zero_phase_samples=phase_zero,cases=by_case,interpretation='Sums of actual enclosing invocation clocks, not phase medians; individual matched ratios retain zero policy; repetitions are not independent workloads; cached local-file CPU experiment only.')
def digest_bytes(b):return hashlib.sha256(b).hexdigest().upper()
if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('directory',type=Path);ap.add_argument('--output',type=Path);a=ap.parse_args();result=audit(a.directory)
    if a.output:
        with a.output.open('x',encoding='utf-8') as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('cases','phases','zero_phase_samples')}))
