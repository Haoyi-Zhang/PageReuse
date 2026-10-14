"""Recompute tables/plot data only from admitted actual full-path records."""
import argparse,csv,json
from pathlib import Path
from check_complete_cost import audit,ARMS,PHASES
from evidence import require
def summarize(directory,output):
    result=audit(directory);output.mkdir(exist_ok=True)
    def save(name,body):
        with (output/name).open('x',encoding='utf-8',newline='') as f:f.write(body)
    save('summary.json',json.dumps(result,indent=2)+'\n')
    labels=('Ordinary exact','Certified incremental','Certified range-min','Certified direct-union')
    rows=[]
    for a,label in zip(ARMS,labels):
        v=result['arms'][a];rows.append(f"{label} & {v['sum_full_wall_seconds']:.6f} & {v['sum_full_process_cpu_seconds']:.6f} & {v['case_median_wall_ratio_above_ordinary']} & {result['zero_full_samples'][a]['cpu']} \\\\")
    save('totals.tex','\\begin{tabular}{@{}lrrrr@{}}\n\\toprule\nPath & Wall sum (s) & CPU sum (s) & Slower inputs & Zero CPU \\\\\n\\midrule\n'+'\n'.join(rows)+'\n\\bottomrule\n\\end{tabular}\n')
    with (output/'phase-costs.csv').open('x',encoding='utf-8',newline='') as f:
        w=csv.writer(f);w.writerow(('arm','phase','sum_wall_seconds','sum_process_cpu_seconds','zero_wall_calls','zero_cpu_calls'))
        for a in ARMS:
            for p in PHASES:
                v=result['phases'][a][p];z=result['zero_phase_samples'][a][p];w.writerow((a,p,v['sum_wall_seconds'],v['sum_process_cpu_seconds'],z['wall'],z['cpu']))
    ordered={a:sorted(v[a]['median_paired_full_wall_ratio'] for v in result['cases'].values()) for a in ARMS[1:]}
    require(all(len(v)==207 for v in ordered.values()),'all inputs for distribution')
    with (output/'case-ratios.csv').open('x',encoding='utf-8',newline='') as f:
        w=csv.writer(f);w.writerow(('rank','percent','incremental','range_min','direct_union'))
        for i in range(207):w.writerow((i+1,100*(i+1)/207,*(ordered[a][i] for a in ARMS[1:])))
    save('startup-build.json',json.dumps(startup(directory),indent=2)+'\n')
    print(json.dumps(dict(status='COMPLETE_COST_TABLES_RECOMPUTED',rows=6624,inputs=207,plot_ranges={a:[v[0],v[-1]] for a,v in ordered.items()},startup_build=startup(directory))))
def startup(d):
    worker=json.loads((d/'worker-process.json').read_text());ready=json.loads((d/'ready.json').read_text());managed=json.loads((d/'managed-build.json').read_text());native=json.loads((d/'native-build.json').read_text())
    return dict(worker_launch_through_ready_wall_seconds=(ready['timestamp']-worker['launch_timestamp'])/worker['frequency'],worker_launch_through_ready_cpu_seconds=ready['process_cpu_seconds'],startup_scope=ready['scope'],managed_build=managed,native_build_wall_seconds=native['build_wall_seconds'],native_compiler_main_process_cpu_seconds=native['compiler_main_process_cpu_seconds'],native_build_process_tree_cpu_seconds=None,whole_worker=worker)
if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('directory',type=Path);ap.add_argument('output',type=Path);a=ap.parse_args();summarize(a.directory,a.output)
