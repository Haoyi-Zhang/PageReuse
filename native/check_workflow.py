"""Audit actual exact-planner document-to-native records; no native execution."""
import argparse, gzip, hashlib, json
from pathlib import Path
from evidence import require, same, loads
import check_policies as semantic

ROOT=Path(__file__).resolve().parents[1]
checker, producer = semantic.module('checker'), semantic.module('producer')
SOURCES={'native/allocator.cpp','native/NativeBridge.cs','native/NativePolicies.cs','native/NativePolicyTests.cs',
         'native/NativeWorkflow.cs','native/workflow.ps1','src/checker.py','src/producer.py'}
EXECUTION_FIELDS={'id','planner','objective','checker','input_bytes','certificate_bytes','certificate','actual_values',
                  'actual_loads','actual_bytes','publications','descriptor_copies','sink','arena_bytes','passed'}

def execution_shape(row):
    require(type(row) is dict and set(row)==EXECUTION_FIELDS, 'complete native execution record fields')

def rows(path):
    path=semantic.actual_record(path);opener=gzip.open if path.suffix=='.gz' else Path.open
    total=0;result=[]
    with opener(path,'rb') as stream:
        while line:=stream.readline(semantic.RECORD_BYTE_CAP-total+1):
            total+=len(line);require(total<=semantic.RECORD_BYTE_CAP,'actual decompressed byte cap')
            result.append(loads(line.decode('utf-8-sig')))
    return result

def audit(directory):
    env=loads((directory/'environment.json').read_text(encoding='utf-8'))
    require(env['protocol']=='exact-document-functional' and env['performance_measurements_started'] is False, 'functional only')
    require(set(env['source_sha256'])==SOURCES, 'all eight actual source bindings')
    require(set(env['record_sha256']) in ({'inputs.jsonl','executions.jsonl','summary.json'},
                                        {'inputs.jsonl.gz','executions.jsonl.gz','summary.json'}), 'complete record bindings')
    require(env['source_sha256']['native/NativePolicyTests.cs']==env['native_policy_tests_compiled_not_invoked_sha256'], 'compiled dependency binding')
    for name,h in env['source_sha256'].items():
        require(semantic.digest(ROOT/name)==h, ('workflow source',name))
    for name,h in env['record_sha256'].items():
        require(semantic.digest(directory/name)==h, ('workflow record',name))
    if 'publication' in env:
        require(env['publication']['operation']=='lossless-gzip-only' and env['publication']['no_rows_removed'] is True, 'lossless publication declaration')
        require(set(env['record_decoded'])=={'inputs.jsonl.gz','executions.jsonl.gz'}, 'full decoded record coverage')
        for name,identity in env['record_decoded'].items():
            require(same(semantic.decoded_identity(directory/name),identity), ('decoded identity',name))
            require(identity['sha256']==env['publication']['original_record_sha256'][name[:-3]], 'original raw bytes retained')
    require(semantic.digest(ROOT/'inputs/traces.jsonl')==env['input_sha256'], 'original corpus binding')
    original={r['id']:r for r in rows(ROOT/'inputs/traces.jsonl')}
    inputs={}
    for r in rows(directory/'inputs.jsonl'):
        id_=r['id'];require(id_ not in inputs, 'duplicate document input')
        require(same(loads(r['input_utf8']),r['trace']), 'serialized input/document correspondence')
        require(r['trace']['visit_weight']==0 and type(r['trace']['visit_weight']) is int, 'fixed common objective')
        if id_ in original:
            require(same(r['trace'],{**original[id_]['trace'],'visit_weight':0}), 'retained graph/bindings/masks, explicitly repriced')
            require(r['suite']=='retained-200' and r['stratum']==original[id_]['stratum'], 'original scope')
        else:
            require(id_ in {'native-wide-repeat','native-wide-rotate','native-wide-recycle','native-edge-capzero','native-edge-empty','native-edge-address64','native-edge-maxcost'} and r['suite']=='native-controls-7', 'separate controls')
        checker.normalize(r['trace']);inputs[id_]=r
    require(len(original)==200 and len(inputs)==207 and set(original)<=set(inputs), 'full unchanged workload denominator')
    expected={id_:producer.solve(r['trace'])['certificate'] for id_,r in inputs.items()}
    seen=set();certificate_bytes=0;input_bytes=0
    for r in rows(directory/'executions.jsonl'):
        execution_shape(r)
        key=r['id'],r['planner'];require(key not in seen and key[0] in inputs and key[1] in ('direct-union','incremental','range-min'), 'matched execution identity')
        seen.add(key);tr=inputs[key[0]]['trace']
        require(r['passed'] is True and r['objective']=='rho0-publication' and r['checker']=='optimality', 'same guarantee')
        require(same(r['certificate'],expected[key[0]]), 'full optimum certificate and earliest-start tie')
        require(checker.check(tr,r['certificate'])['accepted'], 'source-separated strict checker')
        require(same(r['actual_values'],semantic.mandatory_values(tr)), 'actual mandatory byte values')
        for name,n in semantic.accounting(tr,r['certificate']).items():
            if name in r: require(same(r[name],n),('native count',key,name))
        require(same(r['input_bytes'],len(inputs[key[0]]['input_utf8'].encode())), 'acquired input byte count')
        require(same(r['certificate_bytes'],len(json.dumps(r['certificate'],separators=(',',':')).encode())), 'consumed certificate byte count')
        certificate_bytes+=r['certificate_bytes'];input_bytes+=r['input_bytes']
    require(seen=={(id_,p) for id_ in inputs for p in ('direct-union','incremental','range-min')}, '621 actual matched executions')
    summary=loads((directory/'summary.json').read_text())
    require(summary['native_executions']==621 and summary['performance_measurements_started'] is False, 'native completion record')
    result=dict(status='EXACT_DOCUMENT_RECORDS_PASSED',retained_inputs=200,separate_native_controls=7,
                actual_native_executions=621,unique_inputs=207,planners=3,
                serialized_input_bytes_acquired_across_all_calls=input_bytes,
                certificate_bytes_consumed_across_all_calls=certificate_bytes,
                native_timing=False,scope='Functional serialized-input/strict-certificate/native correspondence; byte counts are not latency or independent populations.')
    if (directory/'independent-summary.json').exists():
        require(same(loads((directory/'independent-summary.json').read_text()),result), 'saved independently recomputed summary')
    return result

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('directory',type=Path);ap.add_argument('--output',type=Path);a=ap.parse_args()
    result=audit(a.directory.resolve())
    if a.output:
        with a.output.open('x',encoding='utf-8') as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
