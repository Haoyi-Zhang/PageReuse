"""Real-device conformance for the frozen sequential page traces; no timing study."""
import argparse
import gzip
import hashlib
import json
import platform
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path

from cuda_page_driver import PageDevice, SENTINEL
from evidence import require, same, loads

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import checker
import producer

INPUT = 'results/exact-document-workflow/inputs.jsonl.gz'
SOURCES = ('native/page_loads.ptx', 'native/cuda_page_driver.py', 'native/gpu_pages.py',
           'native/evidence.py', 'src/checker.py', 'src/producer.py', INPUT)
MAX_BYTES = 128 * 1024**2


def bindings():
    return {name: digest(ROOT/name) for name in SOURCES}


def digest(path):
    value, total = hashlib.sha256(), 0
    with path.open('rb') as stream:
        while raw := stream.read(min(1024**2, MAX_BYTES-total+1)):
            total += len(raw)
            require(total <= MAX_BYTES, 'source or compressed record byte budget')
            value.update(raw)
    return value.hexdigest()


def bounded_rows(path):
    result, total = [], 0
    with gzip.open(path, 'rb') as stream:
        while raw := stream.readline(MAX_BYTES-total+1):
            total += len(raw)
            require(total <= MAX_BYTES, 'decompressed record budget')
            result.append(loads(raw.decode()))
    return result


def inputs():
    rows = bounded_rows(ROOT/INPUT)
    require(len(rows) == 207 and len({r['id'] for r in rows}) == 207, '207 distinct frozen inputs')
    for r in rows:
        require(same(loads(r['input_utf8']), r['trace']), 'frozen serialized input')
        checker.normalize(r['trace'])
        require(type(r['trace']['visit_weight']) is int and r['trace']['visit_weight'] == 0, 'fixed objective')
    return rows


def plan(trace, arm):
    if arm == 'exact':
        cert = producer.solve(trace)['certificate']
    else:
        require(arm == 'fresh', 'known arm')
        cert = producer.make_certificate(trace, [[t,t] for t in range(len(trace['steps']))],
                                         [0]*(len(trace['steps'])+1))
    require(checker.check(trace, cert, optimal=arm == 'exact')['accepted'], 'consumed plan')
    return cert


def payload(page, lane):
    width = 2 if page['format'] == 'fp16' else 1
    return (131*page['content'] + 17*page['generation'] + 7*page['kv_group'] + 29*lane) % (1 << (8*width))


def projected(trace, t):
    st = trace['steps'][t]
    mapping = {(b[0], b[1]): b[2] for b in st['bindings']}
    seen, pending, cells = set(), list(st['roots']), set()
    while pending:
        j = pending.pop()
        if j in seen:
            continue
        seen.add(j)
        node = st['nodes'][j]
        pending.extend(node['children'])
        for h, logical, lo, hi in node['atoms']:
            cells.update((mapping[h,logical], lane) for lane in range(lo,hi))
    return sorted(cells)


def shape(trace, cert, t):
    ep = next(e for e in cert['epochs'] if e['start'] <= t <= e['end'])
    B = trace['page_size']
    values, descriptors = [], []
    for desc in ep['pages']:
        p, page = desc[0], trace['pages'][desc[0]]
        width = 2 if page['format'] == 'fp16' else 1
        descriptors.append([p, page['slot'], page['generation'], width, page['length'], page['base']])
        cap = min(page['length'], max(0, trace['steps'][t]['frontier']-page['base']+1))
        values.extend(payload(page, i) if i < cap else SENTINEL for i in range(B))
    return ep, descriptors, values


def control_target(values, B):
    if not values:
        return None
    return next((j for j in range(len(values)//B)
                 if values[j*B:(j+1)*B] == [SENTINEL]*B), 0)


def execute(device, item, arm):
    trace, cert = item['trace'], plan(item['trace'], arm)
    pages, B = trace['pages'], trace['page_size']
    arena_bytes = (max(p['slot'] for p in pages)+1)*2*B
    arena = bytearray([0xD3]*(arena_bytes+64))
    resident = [[0xffffffff,0,0,0] for _ in range(256)]
    device.upload(0, bytes(arena))
    steps, negative, transitions = [], 0, 0
    for t, st in enumerate(trace['steps']):
        for p, page in enumerate(pages):
            if page['last'] == t-1:
                require(resident[page['slot']][0] == p, 'retirement occupant')
                resident[page['slot']] = [0xffffffff,0,0,0]
                transitions += 1
        for p, page in enumerate(pages):
            if page['first'] == t:
                slot = page['slot']
                require(resident[slot][0] == 0xffffffff, 'empty slot at birth')
                width = 2 if page['format'] == 'fp16' else 1
                off = 32+slot*2*B
                arena[off:off+2*B] = bytes([0xA5]*(2*B))
                for i in range(page['length']):
                    value = payload(page,i).to_bytes(width,'little')
                    arena[off+i*width:off+(i+1)*width] = value
                device.upload(0, bytes(arena[off:off+2*B]), off)
                resident[slot] = [p,page['generation'],width,page['length']]
                transitions += 1
        device.upload(1, struct.pack('<1024I', *(x for row in resident for x in row)))
        ep, descriptors, expected = shape(trace,cert,t)
        if t == ep['start']:
            device.upload(2, struct.pack('<'+'I'*6*len(descriptors), *(x for row in descriptors for x in row)))
        actual = device.query(descriptors,B,st['frontier'],arena_bytes)
        require(same(actual,expected), 'all device loads and masked output cells')
        require(device.read(0,arena_bytes+64) == bytes(arena), 'device arena and two guards unchanged')
        indexes = {d[0]:j*B for j,d in enumerate(descriptors)}
        mandatory = [actual[indexes[p]+i] for p,i in projected(trace,t)]
        require(mandatory == [payload(pages[p],i) for p,i in projected(trace,t)], 'mandatory projection')
        # An owned metadata-only negative control; allocated pointers never change.
        rejected = []
        target = control_target(expected,B)
        if descriptors:
            slot = descriptors[target][1]
            changed = [row[:] for row in resident]
            changed[slot][1] = 0  # every admitted generation is positive
            device.upload(1, struct.pack('<1024I', *(x for row in changed for x in row)))
            rejected = device.query(descriptors,B,st['frontier'],arena_bytes)
            expected_control = expected[:]
            expected_control[target*B:(target+1)*B] = [0xffffffff]*B
            require(rejected == expected_control, 'device generation gate including zero cap')
            require(device.read(0,arena_bytes+64) == bytes(arena), 'negative-control arena and guards unchanged')
            device.upload(1, struct.pack('<1024I', *(x for row in resident for x in row)))
            negative += 1
        steps.append(dict(step=t, values=actual, mandatory=mandatory, generation_control=rejected,
                          generation_control_index=target))
    return dict(id=item['id'], arm=arm, certificate=cert, steps=steps,
                transitions=transitions, generation_controls=negative)


def audit(directory):
    with (directory/'summary.json').open('rb') as stream:
        raw = stream.read(2*1024**2+1)
    require(len(raw) <= 2*1024**2, 'summary byte cap')
    saved = loads(raw.decode())
    require(type(saved) is dict and set(saved) == {'observed_utc','environment','source_sha256','counts','record_sha256'}, 'summary fields')
    require(same(saved['source_sha256'],bindings()), 'current source/input correspondence')
    require(digest(directory/'executions.jsonl.gz') == saved['record_sha256'], 'retained record correspondence')
    expected_inputs = {r['id']:r for r in inputs()}
    seen, values, mandatory, steps, controls, transitions = set(), 0, 0, 0, 0, 0
    loaded_lanes, loaded_bytes, zero_caps, zero_controls = 0, 0, 0, 0
    for r in bounded_rows(directory/'executions.jsonl.gz'):
        require(type(r) is dict and set(r) == {'id','arm','certificate','steps','transitions','generation_controls'}, 'execution schema')
        key = r['id'],r['arm']
        require(key not in seen and r['id'] in expected_inputs and r['arm'] in ('fresh','exact'), 'unique execution')
        seen.add(key)
        trace = expected_inputs[r['id']]['trace']
        cert = plan(trace,r['arm'])
        require(same(r['certificate'],cert) and type(r['steps']) is list and len(r['steps']) == len(trace['steps']), 'complete current plan and steps')
        nctrl = 0
        for t,row in enumerate(r['steps']):
            require(type(row) is dict and set(row) == {'step','values','mandatory','generation_control','generation_control_index'} and type(row['step']) is int and row['step'] == t, 'step schema')
            _,ds,expected = shape(trace,cert,t)
            require(same(row['values'],expected), 'complete device result cells')
            require(same(row['mandatory'],[payload(trace['pages'][p],i) for p,i in projected(trace,t)]), 'complete mandatory results')
            B = trace['page_size']
            target = control_target(expected,B)
            require(same(row['generation_control_index'],target), 'explicit controlled descriptor index')
            rejected = expected[:]
            if target is not None:
                zero_controls += expected[target*B:(target+1)*B] == [SENTINEL]*B
                rejected[target*B:(target+1)*B] = [0xffffffff]*B
            require(same(row['generation_control'],rejected), 'complete owned device generation controls')
            for j,d in enumerate(ds):
                n = sum(v != SENTINEL for v in expected[j*B:(j+1)*B])
                loaded_lanes += n; loaded_bytes += n*d[3]; zero_caps += n == 0
            values += len(expected); mandatory += len(row['mandatory']); steps += 1
            nctrl += bool(ds)
        ntrans = sum(1+(p['last'] < len(trace['steps'])-1) for p in trace['pages'])
        require(type(r['transitions']) is int and r['transitions'] == ntrans and type(r['generation_controls']) is int and r['generation_controls'] == nctrl, 'boundary/control counts')
        controls += nctrl; transitions += ntrans
    require(seen == {(id_,arm) for id_ in expected_inputs for arm in ('fresh','exact')}, '414 complete device replays')
    counts = dict(inputs=207,replays=414,queries=steps,output_cells=values,
                  mandatory_values=mandatory,generation_controls=controls,boundary_transitions=transitions,
                  loaded_lanes=loaded_lanes,loaded_bytes=loaded_bytes,zero_cap_consultations=zero_caps,
                  zero_cap_generation_controls=zero_controls)
    require(same(saved['counts'],counts), 'recomputed summary counts')
    return counts


def run(directory):
    require(not directory.exists(), 'fresh output directory; preserve previous attempts')
    before, items, records = bindings(), inputs(), []
    with PageDevice() as device:
        environment = dict(os=platform.platform(),python=sys.version,device=device.info,
                           protocol='synchronous sequential byte conformance; no performance measurement',
                           allocation='persistent bounded device arena; host birth writes precede resident metadata',
                           outputs='all selected B-sized cells including masked sentinels; mandatory atom projection',
                           scope='original synthetic lane arrays; no numerical attention or serving workload')
        for item in items:
            for arm in ('fresh','exact'):
                records.append(execute(device,item,arm))
    require(same(before,bindings()), 'source/input unchanged across actual device execution')
    directory.mkdir(parents=True)
    with gzip.open(directory/'executions.jsonl.gz','wt',encoding='utf-8') as stream:
        for row in records:
            stream.write(json.dumps(row,separators=(',',':'))+'\n')
    counts = dict(inputs=207,replays=414,queries=sum(len(r['steps']) for r in records),
                  output_cells=sum(len(s['values']) for r in records for s in r['steps']),
                  mandatory_values=sum(len(s['mandatory']) for r in records for s in r['steps']),
                  generation_controls=sum(r['generation_controls'] for r in records),
                  boundary_transitions=sum(r['transitions'] for r in records),
                  loaded_lanes=0,loaded_bytes=0,zero_cap_consultations=0,
                  zero_cap_generation_controls=0)
    by_id = {item['id']:item['trace'] for item in items}
    for r in records:
        trace = by_id[r['id']]; B = trace['page_size']
        for t,s in enumerate(r['steps']):
            _,ds,_ = shape(trace,r['certificate'],t)
            target = s['generation_control_index']
            if target is not None:
                counts['zero_cap_generation_controls'] += s['values'][target*B:(target+1)*B] == [SENTINEL]*B
            for j,d in enumerate(ds):
                n = sum(v != SENTINEL for v in s['values'][j*B:(j+1)*B])
                counts['loaded_lanes'] += n; counts['loaded_bytes'] += n*d[3]
                counts['zero_cap_consultations'] += n == 0
    summary = dict(observed_utc=datetime.now(timezone.utc).isoformat(), environment=environment,
                   source_sha256=before,counts=counts,
                   record_sha256=digest(directory/'executions.jsonl.gz'))
    (directory/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    return audit(directory)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('operation',choices=('run','check')); ap.add_argument('directory',type=Path)
    args = ap.parse_args()
    print(json.dumps(run(args.directory) if args.operation == 'run' else audit(args.directory)))
