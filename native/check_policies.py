"""Source-separated functional audit and full-200 cost accounting. No timers.

Reads only owned records/current sources. Uses the original strict checker for
exact arms, safety mode for heuristics, and the original Python policy/DP specs.
"""
from __future__ import annotations
import argparse
import collections
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
from evidence import same, loads as strict_loads

ROOT = Path(__file__).resolve().parents[1]
POLICIES = ('fresh', 'longest-feasible', 'four-step',
            'exact-rho0-range-min', 'exact-rho1-incremental')
SOURCES = ('native/allocator.cpp', 'native/NativeBridge.cs', 'native/NativePolicies.cs',
           'native/NativePolicyTests.cs', 'native/policies.ps1', 'native/check_policies.py',
           'src/producer.py', 'src/checker.py', 'tools/generate.py')


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest().upper()


def check_source_binding(name, expected):
    require(name in SOURCES, f'current source mismatch: {name}')
    if digest(ROOT / name) == expected:
        return
    require(name == 'native/check_policies.py', f'current source mismatch: {name}')
    frozen = strict_loads((ROOT / 'data/measured_policy_checker.json').read_text(encoding='utf-8'))
    require(type(frozen) is dict and set(frozen) == {'path', 'source'}
            and frozen['path'] == name and type(frozen['source']) is str,
            'measured policy checker context')
    require(hashlib.sha256(frozen['source'].encode('utf-8')).hexdigest().upper() == expected,
            'measured policy checker binding')


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'src' / f'{name}.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RECORD_BYTE_CAP = 256 * 1024**2


def actual_record(path):
    if path.suffix != '.gz' and not path.exists():
        path = path.with_name(path.name + '.gz')
    return path


def decoded_identity(path, byte_cap=RECORD_BYTE_CAP):
    path = actual_record(path)
    total, h = 0, hashlib.sha256()
    opener = gzip.open if path.suffix == '.gz' else Path.open
    with opener(path, 'rb') as f:
        while chunk := f.read(min(65536, byte_cap-total+1)):
            total += len(chunk)
            require(total <= byte_cap, f'decompressed record bound: {path.name}')
            h.update(chunk)
    return {'bytes': total, 'sha256': h.hexdigest().upper()}


def read_rows(path, byte_cap=RECORD_BYTE_CAP):
    path = actual_record(path)
    opener = gzip.open if path.suffix == '.gz' else Path.open
    total = 0
    with opener(path, 'rb') as f:
        while line := f.readline(byte_cap-total+1):
            total += len(line)
            require(total <= byte_cap, f'decompressed record bound: {path.name}')
            yield strict_loads(line.decode('utf-8-sig'))


def at_price(trace, price):
    # No payload or graph modifications; neither imported module mutates trace.
    return {**trace, 'visit_weight': price}


def mandatory_values(trace):
    result = []
    for step in trace['steps']:
        bindings = {(b[0], b[1]): b[2] for b in step['bindings']}
        seen, pending, cells = set(), list(step['roots']), set()
        while pending:
            node = pending.pop()
            if node in seen:
                continue
            seen.add(node)
            current = step['nodes'][node]
            pending.extend(current['children'])
            for head, logical, lo, hi in current['atoms']:
                cells.update((bindings[head, logical], lane) for lane in range(lo, hi))
        result.append([payload(trace['pages'][p], lane) for p, lane in sorted(cells)])
    return result


def payload(page, lane):
    width = 2 if page['format'] == 'fp16' else 1
    return (131*page['content'] + 17*page['generation'] + 7*page['kv_group'] + 29*lane) % (1 << (8*width))


def accounting(trace, cert):
    publication = weighted = page_visits = loads = nbytes = copies = sink = 0
    for epoch in cert['epochs']:
        s, t = epoch['start'], epoch['end']
        selected = [d[0] for d in epoch['pages']]
        weight = sum(trace['pages'][p]['weight'] for p in selected)
        publication += trace['setup'] + weight
        weighted += (t-s+1)*weight
        page_visits += (t-s+1)*len(selected)
        copies += len(selected)
        for q in range(s, t+1):
            for p in selected:
                page = trace['pages'][p]
                width = 2 if page['format'] == 'fp16' else 1
                cap = min(page['length'], max(0, trace['steps'][q]['frontier']-page['base']+1))
                loads += cap
                nbytes += cap*width
                for lane in range(cap):
                    sink = (sink*1099511628211 + payload(page, lane)+1) % (1 << 64)
    return dict(publication_cost=publication, weighted_page_visits=weighted, page_visits=page_visits,
                cost_at_fixed_visit_price=publication+weighted, actual_loads=loads,
                actual_bytes=nbytes, publications=len(cert['epochs']), descriptor_copies=copies,
                sink=sink, arena_bytes=(max(p['slot'] for p in trace['pages'])+1)*2*trace['page_size'])


def aggregate(rows, label):
    out = []
    groups = collections.defaultdict(list)
    for row in rows:
        groups[label(row)].append(row)
    for group, members in sorted(groups.items()):
        ratios = [r['publication_cost']/r['rho0_optimum'] for r in members if r['rho0_optimum']]
        out.append(dict(group=group, cases=len(members), valid=len(members), invalid=0,
                        publication_above_rho0_optimum=sum(r['publication_cost'] > r['rho0_optimum'] for r in members),
                        fixed_price_above_rho1_optimum=sum(r['cost_at_fixed_visit_price'] > r['rho1_optimum'] for r in members),
                        maximum_publication_ratio=max(ratios, default=None),
                        zero_publication_optimum_cases=sum(r['rho0_optimum'] == 0 for r in members),
                        sums={k: sum(r[k] for r in members) for k in
                              ('publication_cost', 'weighted_page_visits', 'page_visits', 'cost_at_fixed_visit_price',
                               'actual_loads', 'actual_bytes', 'publications', 'descriptor_copies')}))
    return out


def audit(directory, library=None, managed_assembly=None, build_environment=None, verify_only=False):
    producer, checker = module('producer'), module('checker')
    environment = strict_loads((directory / 'environment.json').read_text(encoding='utf-8-sig'))
    require(environment['mode'] == 'Functional' and environment['performance_measurements_started'] is False, 'functional protocol')
    require(environment['protocol'] == 'matched-five-policy-functional-v1' and environment['policies'] == list(POLICIES), 'five policies')
    require(same(environment['fixed_visit_price'], 1), 'fixed price')
    require(set(environment['source_sha256']) == set(SOURCES), 'source binding coverage')
    for name, expected in environment['source_sha256'].items():
        check_source_binding(name, expected)
    require(digest(ROOT / 'inputs/traces.jsonl') == environment['input_sha256'], 'original input binding')
    require(digest(ROOT / 'results/campaign/certificates.jsonl') == environment['saved_certificate_sha256'], 'saved certificate binding')
    require(environment['runtime_files_distributed'] is False and environment['results_directory'] == 'results/native-policy-comparison', 'public result layout')
    binary_paths = (library, managed_assembly, build_environment)
    require(all(p is None for p in binary_paths) or all(p is not None for p in binary_paths), 'supply all three private binary/build paths, or none for saved-record audit')
    binaries_checked = library is not None
    if binaries_checked:
        require(digest(library) == environment['library_sha256'], 'loaded allocator binary binding')
        require(digest(managed_assembly) == environment['managed_assembly_sha256'], 'managed binary binding')
        require(digest(build_environment) == environment['build_environment_sha256'], 'compilation manifest binding')
        build = strict_loads(build_environment.read_text(encoding='utf-8-sig'))
        require(build['mode'] == 'Compile' and build['source_sha256']['allocator.cpp'] == environment['source_sha256']['native/allocator.cpp']
                and build['library_sha256'] == environment['library_sha256'], 'allocator compilation source/binary match')
    # Binary identities remain recorded when files are not supplied. That mode
    # checks saved data/source bindings, not unavailable runtime files.
    for key in ('library_sha256', 'managed_assembly_sha256', 'build_environment_sha256'):
        require(len(environment[key]) == 64 and all(c in '0123456789ABCDEF' for c in environment[key]), f'recorded identity: {key}')
    require(not any(p.suffix.lower() in {'.dll', '.exe', '.pdb', '.pyc'} for p in directory.rglob('*') if p.is_file()), 'result dataset must not distribute runtime binaries')
    require(set(environment['record_sha256']) == {'cases.jsonl.gz', 'planner-agreement.jsonl.gz', 'policies.jsonl.gz', 'functional-summary.json'}, 'record binding coverage')
    for name, expected in environment['record_sha256'].items():
        require(digest(directory / name) == expected, f'record binding mismatch: {name}')
    compressed = {name for name in environment['record_sha256'] if name.endswith('.gz')}
    require(set(environment['record_decoded']) == compressed, 'decoded binding coverage')
    for name, expected in environment['record_decoded'].items():
            require(same(decoded_identity(directory / name), expected), f'decoded binding mismatch: {name}')

    cases = {}
    for c in read_rows(directory / 'cases.jsonl'):
        require(c['id'] not in cases, 'duplicate case')
        cases[c['id']] = c
    original = {r['id']: r for r in read_rows(ROOT / 'inputs/traces.jsonl')}
    require(len(cases) == 207 and len(original) == 200, 'case denominators')
    for id_, r in original.items():
        c = cases[id_]
        require(same(c['trace'], r['trace']) and c['stratum'] == r['stratum'] and c['suite'] == 'retained-200', f'original trace/stratum: {id_}')
    native = {id_ for id_, c in cases.items() if c['suite'] == 'native-controls-7'}
    require(native == {'native-wide-repeat', 'native-wide-rotate', 'native-wide-recycle', 'native-edge-capzero',
                       'native-edge-empty', 'native-edge-address64', 'native-edge-maxcost'}, 'native control identities')
    require(sum(c['suite'] == 'retained-200' for c in cases.values()) == 200, 'full retained denominator')
    saved = {r['id']: r['certificate'] for r in read_rows(ROOT / 'results/campaign/certificates.jsonl')}
    optima, declared_certificates, values = {}, {}, {}
    for id_, c in cases.items():
        trace = c['trace']
        declared_certificates[id_] = producer.solve(trace)['certificate']
        if id_ in saved:
            require(same(declared_certificates[id_], saved[id_]), f'saved full certificate: {id_}')
        optima[id_] = (producer.solve(at_price(trace, 0))['certificate'], producer.solve(at_price(trace, 1), mode='direct')['certificate'])
        values[id_] = mandatory_values(trace)
    agreed = set()
    for r in read_rows(directory / 'planner-agreement.jsonl'):
        id_ = r['id'];require(id_ not in agreed and id_ in cases, 'agreement case identity');agreed.add(id_)
        require(same(r['declared_visit_weight'], cases[id_]['trace']['visit_weight']), 'original price retained')
        for price, key, expected in ((None, 'declared_certificate', declared_certificates[id_]),
                                     (0, 'rho0_certificate', optima[id_][0]), (1, 'rho1_certificate', optima[id_][1])):
            trace = cases[id_]['trace'] if price is None else at_price(cases[id_]['trace'], price)
            require(same(r[key], expected), f'Python/native full certificate/tie: {id_}/{key}')
            require(checker.check(trace, r[key])['accepted'], f'strict agreement certificate: {id_}/{key}')
    require(agreed == set(cases), '207 agreement records')

    seen, rows = set(), []
    for r in read_rows(directory / 'policies.jsonl'):
        id_, policy = r['id'], r['policy'];key = (id_, policy)
        require(id_ in cases and policy in POLICIES and key not in seen, 'policy/case identity');seen.add(key)
        c = cases[id_];require(r['suite'] == c['suite'] and r['stratum'] == c['stratum'], 'stratum identity')
        price = 1 if policy == POLICIES[4] else 0
        optimal = policy in POLICIES[3:]
        trace = at_price(c['trace'], price)
        require(same(r['planning_visit_weight'], price) and r['checker'] == ('optimality' if optimal else 'safety-only'), 'fair checker/price')
        cert = r['certificate'];require(checker.check(trace, cert, optimal=optimal)['accepted'], f'checker: {key}')
        if optimal:
            expected = optima[id_][price]
        else:
            kind = {'fresh': 'fresh', 'longest-feasible': 'greedy', 'four-step': 'periodic'}[policy]
            cuts = producer.baseline(trace, kind)['cuts']
            expected = producer.make_certificate(trace, cuts, [0]*(len(trace['steps'])+1))
        require(same(cert, expected), f'complete plan/tie/spec: {key}')
        counts = accounting(trace, cert)
        for k, v in counts.items():
            require(same(r[k], v), f'native accounting {key}/{k}')
        require(cert['total_cost'] == counts['publication_cost'] + price*counts['weighted_page_visits'], 'objective identity')
        require(same(r['actual_values'], values[id_]) and r['passed'] is True, f'mandatory values: {key}')
        require(same(r['rho0_optimum'], optima[id_][0]['total_cost']) and same(r['rho1_optimum'], optima[id_][1]['total_cost']), 'paired optimum accounting')
        require(r['publication_cost'] >= r['rho0_optimum'] and r['cost_at_fixed_visit_price'] >= r['rho1_optimum'], 'feasible lower bounds')
        rows.append(r)
    require(seen == {(id_, p) for id_ in cases for p in POLICIES}, '1035 matched policy records')
    functional = strict_loads((directory / 'functional-summary.json').read_text())
    expected_functional = dict(status='FUNCTIONAL_PASSED', native_policy_replays=1035,
        retained_cases=200, native_controls=7, targeted_controls=134,
        performance_measurements_started=False)
    require(all(same(functional[k], v) for k,v in expected_functional.items()), 'native functional summary')
    retained = [r for r in rows if r['suite'] == 'retained-200']
    summary = dict(status='SOURCE_SEPARATED_FUNCTIONAL_PASSED', retained_cases=200, retained_policy_records=len(retained),
                   native_control_cases=7, native_policy_records=len(rows)-len(retained), full_certificate_agreement_cases=207,
                   original_nonzero_price_cases=[id_ for id_, c in cases.items() if c['trace']['visit_weight'] != 0],
                   fixed_visit_price=1, performance_measurements_started=False,
                   environment_sha256=digest(directory / 'environment.json'),
                   full200_by_policy=aggregate(retained, lambda r: r['policy']),
                   full200_by_stratum_and_policy=aggregate(retained, lambda r: (r['stratum'], r['policy'])),
                   full200_by_family_and_policy=aggregate(retained, lambda r: (r['stratum'].split('-')[0], r['policy'])),
                   separate_native_controls=aggregate([r for r in rows if r['suite'] != 'retained-200'], lambda r: (r['stratum'], r['policy'])),
                   interpretation='Synthetic case frequencies are not serving prevalence. Publication and fixed-price objectives are reported separately; loads/bytes are counts, not speed.')
    target = directory / 'independent-summary.json'
    if verify_only:
        # JSON arrays deserialize as lists; normalize in-memory tuple group keys
        # through the same serialization before comparing the saved summary.
        require(target.exists() and same(strict_loads(target.read_text(encoding='utf-8')),
                strict_loads(json.dumps(summary))), 'saved summary differs from recomputed records')
    else:
        require(not target.exists(), 'preserve prior independent summary; use --verify-only to recheck it')
        target.write_text(json.dumps(summary, indent=2, sort_keys=True)+'\n', encoding='utf-8')
    print(json.dumps(dict(binary_files_checked=binaries_checked, verify_only=verify_only,
                         **{k: summary[k] for k in ('status', 'retained_cases', 'retained_policy_records',
                                             'native_control_cases', 'native_policy_records', 'full_certificate_agreement_cases',
                                             'performance_measurements_started')})))
    for r in summary['full200_by_policy']:
        print(json.dumps(r, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--library', type=Path)
    parser.add_argument('--managed-assembly', type=Path)
    parser.add_argument('--build-environment', type=Path)
    parser.add_argument('--verify-only', action='store_true', help='Recompute and compare the existing summary without writing or executing native code.')
    args = parser.parse_args()
    audit(args.directory.resolve(), *(p.resolve() if p is not None else None for p in
          (args.library, args.managed_assembly, args.build_environment)), verify_only=args.verify_only)
