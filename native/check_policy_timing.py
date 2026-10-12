"""Binary-free verification of the saved current five-policy timing campaign.

Recomputes every functional vector/count/plan and every fixed-round ratio.
No native execution, timers, filtering, source mutation, or performance tuning.
The runtime compared each timed vector before omitting it from the raw clock
record; that comparison is recorded evidence, not a second per-call replay here.
"""
from __future__ import annotations
import argparse
import collections
import csv
import gzip
import hashlib
import importlib.util
import itertools
import io
import json
import platform
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAP = 256 * 1024**2
POLICIES = ('fresh', 'longest-feasible', 'four-step', 'exact-rho0-range-min', 'exact-rho1-incremental')
PANEL = ('case-000', 'case-001', 'case-003', 'case-004', 'case-005', 'case-056', 'case-120',
         'case-160', 'case-184', 'case-196', 'case-199', 'native-wide-repeat', 'native-wide-rotate', 'native-wide-recycle')
CORE = ('native/allocator.cpp', 'native/NativeBridge.cs', 'native/NativePolicies.cs', 'native/NativePolicyTests.cs',
        'native/policies.ps1', 'native/check_policies.py', 'src/producer.py', 'src/checker.py', 'tools/generate.py')
SOURCES = CORE + ('native/NativePolicyTiming.cs', 'native/time_policies.ps1')
PHASES = ('planner_ticks', 'checking_ticks', 'complete_ticks')


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest().upper()


def content(path):
    opener = gzip.open if path.suffix == '.gz' else Path.open
    with opener(path, 'rb') as f:
        data = f.read(CAP + 1)
    need(len(data) <= CAP, f'actual decompressed-byte cap: {path.name}')
    return data


def decoded(path):
    data = content(path)
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest().upper()}


def rows(path):
    return [json.loads(line) for line in content(path).decode('utf-8-sig').splitlines() if line]


def read_json(path):
    return json.loads(content(path).decode('utf-8-sig'))


def module(path, name):
    # These are the hash-verified, previously reviewed pure Python specifications;
    # no snapshot shell/native program is executed.
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def safe_file(base, relative):
    path = (base / relative).resolve()
    need(path.is_relative_to(base.resolve()) and path.is_file(), f'snapshot path: {relative}')
    return path


def verify(directory, require_current=False, library=None, assembly=None):
    env = read_json(directory / 'environment.json')
    need(env['mode'] == 'Measure' and env['protocol'] == 'current-five-policy-timing'
         and env['performance_measurements_started'] is True, 'completed current timing environment')
    need(env['runtime_files_distributed'] is False and env['affinity'] == 1 and env['cpu_threads'] == 1, 'native runtime/affinity declarations')
    need(env['wall_limit_seconds'] <= 120 and env['memory_limit_mib'] <= 1024, 'worker caps')
    need(env['python_used'] is False and env['python_version'] is None, 'no Python in measurement path')
    p = env['protocol_details']
    need(p['panel'] == list(PANEL) and p['policies'] == list(POLICIES), 'fixed workload/policy identities')
    need((p['warmup_complete_calls_per_arm'], p['rounds'], p['calls_per_arm_per_round'],
          p['expected_clock_samples'], p['fixed_visit_price']) == (3, 11, 4, 3080, 1), 'fixed counts and price')
    need(env['clock']['name'] == 'System.Diagnostics.Stopwatch' and env['clock']['zero_ticks_retained'] is True
         and type(env['clock']['frequency']) is int and env['clock']['frequency'] > 0, 'clock identity/frequency')
    need(digest(directory / 'source-manifest.json') == env['source_manifest_sha256'], 'source manifest binding')
    need(digest(directory / 'input-manifest.json') == env['input_manifest_sha256'], 'input manifest binding')
    source = read_json(directory / 'source-manifest.json')
    inputs = read_json(directory / 'input-manifest.json')
    need(source['snapshot'] == 'measured-source' and inputs['snapshot'] == 'measured-input', 'snapshot roots')
    need(set(source['source_sha256']) == set(SOURCES), 'all measured source bindings')
    source_root, input_root = directory / 'measured-source', directory / 'measured-input'
    for name, h in source['source_sha256'].items():
        need(digest(safe_file(source_root, name)) == h, f'measured source snapshot: {name}')
        if require_current:
            need(digest(ROOT / name) == h, f'current source differs from timing: {name}')
    for name, identity in inputs['files'].items():
        path = safe_file(input_root, name)
        need(digest(path) == identity['sha256'] and decoded(path) == identity['decoded'], f'input snapshot: {name}')
    need(set(inputs['files']) == {'inputs/traces.jsonl.gz', 'results/campaign/certificates.jsonl.gz',
                                 'panel.jsonl.gz', 'functional-values.jsonl.gz', 'native-build-environment.json',
                                 'functional/environment.json', 'functional/independent-summary.json',
                                 'functional/cases.jsonl.gz', 'functional/planner-agreement.jsonl.gz',
                                 'functional/policies.jsonl.gz', 'functional/functional-summary.json'}, 'input coverage')
    build = read_json(input_root / 'native-build-environment.json')
    need(build['mode'] == 'Compile' and build['source_sha256']['allocator.cpp'] == source['source_sha256']['native/allocator.cpp'], 'native compilation source')
    need(build['library_sha256'] == source['native_library_sha256'] == env['library_sha256'], 'native binary recorded identity')
    need(source['managed_assembly_sha256'] == env['managed_assembly_sha256'], 'new managed binary recorded identity')
    public_build_digest = digest(input_root / 'native-build-environment.json')
    if 'provenance_sha256' in env:
        provenance = read_json(directory / 'provenance.json')
        need(digest(directory / 'provenance.json') == env['provenance_sha256'], 'public provenance binding')
        need(provenance['kind'] == 'public-private-path-omission'
             and provenance['omitted_fields'] == ['measured-input/native-build-environment.json:compiler_path']
             and 'compiler_path' not in build, 'only private compiler-path omission')
        need(provenance['original_native_build_environment_sha256'] == env['build_environment_sha256']
             == inputs['files']['native-build-environment.json']['original_sha256'], 'original build manifest identity preserved')
        need(provenance['unchanged_source_manifest_sha256'] == env['source_manifest_sha256']
             and provenance['unchanged_record_sha256'] == env['record_sha256'], 'source/raw clocks preserved during publication')
        semantic_build_digest = hashlib.sha256(json.dumps(build, sort_keys=True, separators=(',', ':')).encode()).hexdigest().upper()
        need(semantic_build_digest == provenance['native_build_semantic_sha256'], 'all substantive native build fields preserved')
    else:
        need(public_build_digest == env['build_environment_sha256'], 'actual copied build manifest')
    need(env['native_compiler'] == build['compiler'] and env['native_compiler_flags'] == build['compiler_flags']
         and source['managed_compiler_flags'] == env['managed_compiler_flags'] == '/optimize+', 'compiler flags/origin')
    need((library is None) == (assembly is None), 'supply both private binaries or neither')
    if library is not None:
        need(digest(library) == env['library_sha256'] and digest(assembly) == env['managed_assembly_sha256'], 'actual private binary identities')
    need(not any(f.suffix.lower() in {'.dll', '.exe', '.pdb', '.pyc'} for f in directory.rglob('*') if f.is_file()), 'dataset must be binary-free')
    need(set(env['record_sha256']) == {'samples.jsonl.gz', 'timing-summary.json'}, 'raw record coverage')
    for name, h in env['record_sha256'].items():
        need(digest(directory / name) == h, f'raw record binding: {name}')
    need(env['record_decoded'] == {'samples.jsonl.gz': decoded(directory / 'samples.jsonl.gz')}, 'complete raw gzip identity')

    functional = input_root / 'functional'
    fe = read_json(functional / 'environment.json')
    fs = read_json(functional / 'independent-summary.json')
    fn = read_json(functional / 'functional-summary.json')
    need(digest(functional / 'environment.json') == inputs['functional_environment_sha256'] == fs['environment_sha256'], 'functional environment binding')
    need(digest(functional / 'independent-summary.json') == inputs['functional_summary_sha256'], 'functional summary binding')
    need(fe['performance_measurements_started'] is False and fe['mode'] == 'Functional', 'functional/timing evidence distinct')
    need(set(fe['source_sha256']) == set(CORE), 'functional source coverage')
    for name, h in fe['source_sha256'].items():
        need(h == source['source_sha256'][name], f'functional source differs: {name}')
    for name, h in fe['record_sha256'].items():
        need(digest(functional / name) == h, f'functional record: {name}')
    for name, identity in fe['record_decoded'].items():
        need(decoded(functional / name) == identity, f'functional decoded record: {name}')
    need(fn['status'] == 'FUNCTIONAL_PASSED' and fn['native_policy_replays'] == 1035 and fn['targeted_controls'] == 134,
         'required native functional coverage')
    need(fs['status'] == 'SOURCE_SEPARATED_FUNCTIONAL_PASSED' and fs['retained_policy_records'] == 1000
         and fs['native_policy_records'] == 35, 'required source-separated functional coverage')
    need(fe['library_sha256'] == env['library_sha256'], 'same current native allocator')
    for name, h in inputs['original_input_sha256'].items():
        need(decoded(input_root / (name + '.gz'))['sha256'] == h, f'original input binding: {name}')
    need(fe['input_sha256'] == inputs['original_input_sha256']['inputs/traces.jsonl']
         and fe['saved_certificate_sha256'] == inputs['original_input_sha256']['results/campaign/certificates.jsonl'], 'same original inputs/certificates')
    if require_current:
        for name, h in inputs['original_input_sha256'].items():
            need(digest(ROOT / name) == h, f'current original input: {name}')
        need(digest(ROOT / 'results/native-policy-comparison/environment.json') == inputs['functional_environment_sha256'], 'current functional dataset binding')

    checker = module(source_root / 'src/checker.py', 'saved_timing_checker')
    producer = module(source_root / 'src/producer.py', 'saved_timing_producer')
    semantic = module(source_root / 'native/check_policies.py', 'saved_timing_accounting')
    cases = {r['id']: r for r in rows(functional / 'cases.jsonl.gz')}
    originals = {r['id']: r for r in rows(input_root / 'inputs/traces.jsonl.gz')}
    saved = {r['id']: r['certificate'] for r in rows(input_root / 'results/campaign/certificates.jsonl.gz')}
    need(len(cases) == 207 and len(originals) == len(saved) == 200, 'original/functional denominators')
    for id_, r in originals.items():
        need(cases[id_]['trace'] == r['trace'] and cases[id_]['stratum'] == r['stratum'], f'original trace/stratum: {id_}')
    golden = {}
    for id_, case in cases.items():
        trace = case['trace']
        golden[id_] = semantic.mandatory_values(trace)
        if id_ in saved:
            need(producer.solve(trace)['certificate'] == saved[id_], f'saved full certificate: {id_}')
    functional_rows = {}
    for r in rows(functional / 'policies.jsonl.gz'):
        id_, policy = r['id'], r['policy'];key = (id_, policy)
        need(id_ in cases and policy in POLICIES and key not in functional_rows, 'functional policy identity')
        price = int(policy == POLICIES[4]);optimal = policy in POLICIES[3:]
        trace = {**cases[id_]['trace'], 'visit_weight': price}
        need(r['planning_visit_weight'] == price and r['checker'] == ('optimality' if optimal else 'safety-only'), 'appropriate functional checker/objective')
        need(checker.check(trace, r['certificate'], optimal=optimal)['accepted'], f'functional checker: {key}')
        if optimal:
            expected = producer.solve(trace)['certificate']
        else:
            kind = {'fresh': 'fresh', 'longest-feasible': 'greedy', 'four-step': 'periodic'}[policy]
            expected = producer.make_certificate(trace, producer.baseline(trace, kind)['cuts'], [0]*(len(trace['steps'])+1))
        need(r['certificate'] == expected and r['actual_values'] == golden[id_], f'functional full plan/tie/vector: {key}')
        for name, expected_count in semantic.accounting(trace, r['certificate']).items():
            need(r[name] == expected_count, f'functional count/sink: {key}/{name}')
        functional_rows[key] = r
    need(set(functional_rows) == set(itertools.product(cases, POLICIES)), '1035 functional rows')
    references = rows(input_root / 'functional-values.jsonl.gz')
    need(len(references) == 70, 'complete timing reference count')
    reference_keys = set()
    for r in references:
        key = (r['id'], r['policy']);need(key not in reference_keys and key[0] in PANEL, 'unique panel reference')
        need(r == functional_rows[key], f'complete reference unchanged: {key}');reference_keys.add(key)
    need(reference_keys == set(itertools.product(PANEL, POLICIES)), '70 matched complete functional references')
    panel = rows(input_root / 'panel.jsonl.gz')
    need([r['id'] for r in panel] == list(PANEL), 'original fixed panel/order')
    for r in panel:
        need(r['trace'] == cases[r['id']]['trace'], f'actual panel input unchanged: {r["id"]}')

    samples = rows(directory / 'samples.jsonl.gz')
    expected_order = [(id_, r, pos, c, POLICIES[(r+pos) % 5]) for id_ in PANEL for r in range(11) for pos in range(5) for c in range(4)]
    need(len(samples) == len(expected_order) == 3080, 'all individual clock samples retained')
    clock = env['clock']['frequency'];blocks = collections.defaultdict(lambda: [0]*11);zeros = dict.fromkeys(PHASES, 0)
    counts = {'actual_loads': 'actual_loads', 'actual_bytes': 'actual_bytes', 'publications': 'publications',
              'descriptor_copies': 'descriptor_copies', 'sink': 'sink', 'arena_bytes': 'arena_bytes'}
    for r, expected_key in zip(samples, expected_order):
        need((r['id'], r['round'], r['position'], r['call'], r['policy']) == expected_key, 'fixed sample sequence/rotation')
        need(r['frequency'] == clock and r['correct'] is True and r['complete_values_checked_outside_timer'] is True
             and r['failure_phase'] is None and r['error'] is None and r['complete_is_phase_sum'] is False, 'successful actual complete-path sample')
        policy = r['policy'];need(r['planning_visit_weight'] == int(policy == POLICIES[4])
                                 and r['checker'] == ('optimality' if policy in POLICIES[3:] else 'safety-only'), 'timed checker/objective')
        need(r['functional_reference'] == r['id'] + '/' + policy, 'full vector reference binding')
        reference = functional_rows[r['id'], policy]
        for name, field in counts.items():
            need(r[name] == reference[field], f'actual timed native count/sink: {name}')
        for phase in PHASES:
            ticks = r[phase];need(type(ticks) is int and ticks >= 0, 'raw nonnegative integer clocks, including zero')
            blocks[r['id'], policy, phase][r['round']] += ticks
            zeros[phase] += ticks == 0
    native_summary = read_json(directory / 'timing-summary.json')
    need(native_summary['status'] == 'TIMING_COMPLETED' and native_summary['raw_clock_samples'] == native_summary['verified_complete_calls'] == 3080
         and native_summary['warmup_calls'] == 210 and native_summary['rounds'] == 11 and native_summary['calls_per_arm'] == 4, 'native completion accounting')
    need(native_summary['zero_tick_calls'] == {name.replace('_ticks', ''): n for name, n in zeros.items()}, 'quantization accounting')
    need(native_summary['filtering'] == 'none' and native_summary['price_tuning'] is False and native_summary['seed_selection'] is False
         and native_summary['forced_gc'] is False, 'fixed untuned retention')

    pairs = []
    for id_, phase, reference, target in itertools.product(PANEL, PHASES, POLICIES, POLICIES):
        if reference == target:
            continue
        a, b = blocks[id_, target, phase], blocks[id_, reference, phase]
        ratios = [x/y if y else None for x, y in zip(a, b)]
        defined = [v for v in ratios if v is not None]
        pairs.append(dict(id=id_, phase=phase, reference=reference, target=target, target_four_call_ticks=a, reference_four_call_ticks=b,
                          round_ratios=ratios, median_ratio=statistics.median(defined) if defined else None,
                          min_ratio=min(defined, default=None), max_ratio=max(defined, default=None),
                          slower_rounds=sum(x > y for x, y in zip(a, b)), tied_rounds=sum(x == y for x, y in zip(a, b)),
                          faster_rounds=sum(x < y for x, y in zip(a, b)), undefined_zero_reference_rounds=sum(y == 0 for y in b)))
    complete = [r for r in pairs if r['phase'] == 'complete_ticks']
    aggregate = []
    for reference, target in itertools.permutations(POLICIES, 2):
        members = [r for r in complete if r['reference'] == reference and r['target'] == target]
        aggregate.append(dict(reference=reference, target=target, cases=14, paired_rounds=154,
                              slower_rounds=sum(r['slower_rounds'] for r in members), tied_rounds=sum(r['tied_rounds'] for r in members),
                              faster_rounds=sum(r['faster_rounds'] for r in members),
                              all_11_rounds_slower_cases=[r['id'] for r in members if r['slower_rounds'] == 11],
                              case_median_slower_cases=[r['id'] for r in members if r['median_ratio'] is not None and r['median_ratio'] > 1],
                              undefined_rounds=sum(r['undefined_zero_reference_rounds'] for r in members)))
    absolute = []
    for id_, policy in itertools.product(PANEL, POLICIES):
        absolute.append(dict(id=id_, policy=policy,
                             median_round_mean_ns={phase: statistics.median(blocks[id_, policy, phase])*1e9/(4*clock) for phase in PHASES},
                             complete_ratio_to_fresh=next((r['median_ratio'] for r in complete if r['id'] == id_ and r['reference'] == 'fresh' and r['target'] == policy), 1.0)))
    retained_rows = [r for r in functional_rows.values() if cases[r['id']]['suite'] == 'retained-200']
    full200 = semantic.aggregate(retained_rows, lambda r: r['policy'])
    need(full200 == fs['full200_by_policy'], 'full200 baseline summary reproduced')
    summary = dict(status='SAVED_CURRENT_TIMING_CHECKS_PASSED', verifier_sha256=digest(Path(__file__)),
                   timing_environment_sha256=digest(directory / 'environment.json'), sample_file='samples.jsonl.gz',
                   cases=14, policies=list(POLICIES), rounds=11, calls_per_arm_per_round=4, raw_samples=3080,
                   functional_rows_rechecked=1035, functional_vectors_reconstructed=207, targeted_native_controls_recorded=134,
                   scalar_native_output_records_rechecked=3080, full_panel_reference_vectors=70, zero_tick_calls=zeros,
                   paired_ratio_definition='For each case/round/phase: sum of target four separately timed calls / sum of reference four calls. Median of all 11 ratios; undefined zero-denominator ratios retained as null, not filtered for performance.',
                   absolute_time_definition='Median across 11 rounds of the mean of four measured calls; complete times are actual complete ReplayPolicy timers, not phase sums.',
                   value_evidence='Every timed execution performed a full-vector comparison outside its timer in the bound C# source. Raw clocks omit repeated vectors; complete functional reference vectors are retained and reconstructed here. No second per-call native replay is claimed.',
                   paired_ratio_records=840, paired_ratio_file='paired-ratios.jsonl.gz', complete_comparisons=aggregate, absolute_by_case_policy=absolute,
                   full200_by_policy=full200,
                   guarantees='Safety-only heuristics versus exact rho0 publication and exact rho1 visit-priced guarantees; shared native projection, different selected extra loads.',
                   limits='One fixed synthetic CPU campaign. No filtering, chosen-best repeat, serving-population, GPU attention, deployment or acceptance conclusion.')
    return summary, pairs, library is not None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('directory', type=Path)
    ap.add_argument('--write-summary', action='store_true')
    ap.add_argument('--verify-only', action='store_true')
    ap.add_argument('--require-current-sources', action='store_true')
    ap.add_argument('--library', type=Path)
    ap.add_argument('--managed-assembly', type=Path)
    args = ap.parse_args();need(not (args.write_summary and args.verify_only), 'choose write or verify, not both')
    directory = args.directory.resolve()
    summary, pairs, binary_check = verify(directory, args.require_current_sources, args.library, args.managed_assembly)
    text = ''.join(json.dumps(r, sort_keys=True, separators=(',', ':'))+'\n' for r in pairs).encode()
    target, pair_file = directory / 'independent-summary.json', directory / 'paired-ratios.jsonl.gz'
    summary['paired_ratio_decoded'] = {'bytes': len(text), 'sha256': hashlib.sha256(text).hexdigest().upper()}
    tables = {}
    out = io.StringIO(newline='');writer = csv.writer(out, lineterminator='\n')
    writer.writerow(['id', *POLICIES[1:]])
    for id_ in PANEL:
        writer.writerow([id_, *[format(next(r['complete_ratio_to_fresh'] for r in summary['absolute_by_case_policy']
                                            if r['id'] == id_ and r['policy'] == policy), '.9f') for policy in POLICIES[1:]]])
    tables['complete-ratios.csv'] = out.getvalue().encode()
    out = io.StringIO(newline='');writer = csv.writer(out, lineterminator='\n')
    writer.writerow(['policy', 'valid', 'invalid', 'publication_above_rho0_optimum', 'maximum_publication_ratio',
                     'fixed_price_above_rho1_optimum', 'publication_cost_sum', 'weighted_page_visits_sum', 'native_loads_sum', 'native_bytes_sum'])
    for policy in POLICIES:
        r = next(r for r in summary['full200_by_policy'] if r['group'] == policy)
        writer.writerow([policy, r['valid'], r['invalid'], r['publication_above_rho0_optimum'], format(r['maximum_publication_ratio'], '.9f'),
                         r['fixed_price_above_rho1_optimum'], r['sums']['publication_cost'], r['sums']['weighted_page_visits'],
                         r['sums']['actual_loads'], r['sums']['actual_bytes']])
    tables['full200-baselines.csv'] = out.getvalue().encode()
    summary['paper_table_sha256'] = {name: hashlib.sha256(data).hexdigest().upper() for name, data in tables.items()}
    if args.write_summary:
        need(not target.exists() and not pair_file.exists() and not any((directory/name).exists() for name in tables), 'never overwrite an earlier analysis')
        pair_file.write_bytes(gzip.compress(text, compresslevel=9, mtime=0))
        target.write_text(json.dumps(summary, sort_keys=True, indent=2)+'\n', encoding='utf-8')
        for name, data in tables.items():
            (directory/name).write_bytes(data)
    if args.verify_only:
        need(read_json(target) == summary and content(pair_file) == text, 'saved summaries/paired ratios differ from fixed-round recomputation')
        for name, data in tables.items():
            need((directory/name).read_bytes() == data, f'paper table differs from raw recomputation: {name}')
    print(json.dumps(dict(status=summary['status'], raw_samples=3080, functional_rows_rechecked=1035,
                          paired_ratio_records=840, binary_files_checked=binary_check, verification_python=platform.python_version())))
    for r in summary['complete_comparisons']:
        if r['reference'] == 'fresh':
            print(json.dumps(r, sort_keys=True))


if __name__ == '__main__':
    main()
