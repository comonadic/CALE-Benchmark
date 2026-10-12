#!/usr/bin/env python3
"""Static Harbor package preflight; runtime and professional quality remain untested."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import tomllib


def validate(path, require_harbor=False):
    p=Path(path).resolve()
    errors=[]
    required=['instruction.md','task.toml','environment/Dockerfile','solution/solve.sh','tests/test.sh']
    hashes={}
    for rel in required:
        q=p/rel
        if not q.is_file() or q.stat().st_size==0:
            errors.append(f'Missing or empty {rel}')
        else:
            hashes[rel]=hashlib.sha256(q.read_bytes()).hexdigest()
    cfg={}
    try:
        cfg=tomllib.loads((p/'task.toml').read_text())
    except (OSError,ValueError) as exc:
        errors.append(f'Invalid task.toml: {exc}')
    inputs=p/'environment/input-data'
    if not inputs.exists() or not any(q.is_file() and q.stat().st_size for q in inputs.rglob('*')):
        errors.append('No nonempty visible input files')
    if cfg.get('verifier',{}).get('environment_mode')=='separate':
        q=p/'tests/Dockerfile'
        if not q.is_file() or not q.stat().st_size:
            errors.append('Separate verifier requires tests/Dockerfile in this delivery contract')
    rubrics=sorted((p/'tests').glob('*rubric*.json'))
    for q in rubrics:
        try:
            rubric=json.loads(q.read_text())
            total=rubric.get('total_points')
            if total is not None and (isinstance(total,bool) or not isinstance(total,(int,float)) or not math.isfinite(total) or total<=0):
                errors.append(f'{q.name}: invalid total_points')
            for group in ['criteria','objective_criteria']:
                rows=rubric.get(group,[])
                identifiers=[]
                for item in rows:
                    ident=item.get('id',item.get('criterion_id',item.get('label')))
                    if ident is not None:
                        identifiers.append(ident)
                    pts=item.get('points')
                    if isinstance(pts,bool) or not isinstance(pts,(int,float)) or not math.isfinite(pts) or pts<0:
                        errors.append(f'{q.name}: invalid criterion points')
                if len(set(identifiers))!=len(identifiers):
                    errors.append(f'{q.name}: duplicate {group} identifiers')
        except (ValueError,AttributeError,TypeError) as exc:
            errors.append(f'{q.name}: invalid rubric: {exc}')
    harbor_status='not_available'
    try:
        from harbor.models.task.task import Task
        Task(p).config
        harbor_status='passed'
    except ImportError:
        if require_harbor:
            errors.append('Harbor is required but unavailable')
    except Exception as exc:
        harbor_status='failed'
        errors.append(f'Harbor parsing failed: {type(exc).__name__}: {exc}')
    return {'task':p.name,'path':str(p),'static_preflight':'passed' if not errors else 'failed','harbor_schema':harbor_status,'errors':errors,'entrypoint_sha256':hashes,'runtime_validation':'not_run','professional_quality':'not_evaluated'}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('paths',nargs='+')
    parser.add_argument('--require-harbor',action='store_true')
    args=parser.parse_args()
    records=[validate(p,args.require_harbor) for p in args.paths]
    print(json.dumps({'results':records},ensure_ascii=False,indent=2))
    raise SystemExit(any(r['errors'] for r in records))
