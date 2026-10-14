"""Materialize the frozen 207 serialized documents into a fresh private directory."""
import argparse,hashlib,json
from pathlib import Path
import check_workflow as workflow
from evidence import require,same
ROOT=Path(__file__).resolve().parents[1]
def prepare(output):
    output=output.resolve();require(not output.is_relative_to(ROOT),'input runtime must remain private')
    source=ROOT/'results/exact-document-workflow/inputs.jsonl.gz';output.mkdir()
    records=workflow.rows(source);require(len(records)==207,'complete frozen input set');files={};index=[]
    for r in records:
        id_=r['id'];require(type(id_) is str and id_.startswith(('case-','native-')) and '/' not in id_ and '\\' not in id_,'owned identifier')
        require(same(workflow.loads(r['input_utf8']),r['trace']),'exact frozen JSON bytes')
        require(type(r['trace']['visit_weight']) is int and r['trace']['visit_weight']==0,'same rho=0')
        name=id_+'.json';require(name not in files,'unique input identity');raw=r['input_utf8'].encode()
        (output/name).write_bytes(raw);files[name]=hashlib.sha256(raw).hexdigest();index.append({k:r[k] for k in ('id','suite','stratum')})
    (output/'index.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in index),encoding='utf-8')
    manifest=dict(files=files,frozen_inputs_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),index_sha256=hashlib.sha256((output/'index.jsonl').read_bytes()).hexdigest(),input_count=207,input_bytes=sum((output/n).stat().st_size for n in files))
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(dict(status='ALL_FROZEN_DOCUMENTS_MATERIALIZED',inputs=207,input_bytes=manifest['input_bytes'],frozen_inputs_sha256=manifest['frozen_inputs_sha256'])))
if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('output',type=Path);a=ap.parse_args();prepare(a.output)
