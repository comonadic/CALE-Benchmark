#!/usr/bin/env python3
"""Build complete agent and separate-verifier images from their declared contexts."""
import argparse,hashlib,json,os,subprocess,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def tree_hash(path):
    h=hashlib.sha256()
    for p in sorted(path.rglob('*')):
        if p.is_file() and '__pycache__' not in p.parts:
            h.update(str(p.relative_to(path)).encode()+b'\0'+hashlib.sha256(p.read_bytes()).digest())
    return h.hexdigest()

def build(args):
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    command=['docker']
    if args.docker_host:command+=['--host',args.docker_host]
    if args.docker_config:command+=['--config',str(args.docker_config)]
    records=[]
    for task in sorted((ROOT/'tasks').iterdir()):
        if not (task/'task.toml').is_file():continue
        record={'task_id':task.name,'context':{}}
        for role,directory in [('agent','environment'),('verifier','tests')]:
            context=task/directory
            fingerprint=tree_hash(context)
            tag=f'cale-{task.name}-{role}:{fingerprint[:12]}'
            started=time.monotonic()
            cmd=command+['build','--tag',tag,'--label','org.cale.task='+task.name,'--label','org.cale.role='+role,'--label','org.cale.context-sha='+fingerprint,'--file',str(context/'Dockerfile')]
            if args.build_proxy:
                cmd+=['--build-arg','HTTP_PROXY='+args.build_proxy,'--build-arg','HTTPS_PROXY='+args.build_proxy]
            cmd+=[str(context)]
            with (out/f'{task.name}-{role}.build.log').open('w') as log:
                subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True)
            ident=subprocess.check_output(command+['image','inspect',tag,'--format','{{.Id}}'],text=True).strip()
            record[role]=ident
            record['context'][role]={'tree_sha256':fingerprint,'tag':tag,'build_seconds':round(time.monotonic()-started,3)}
            print(json.dumps({'task_id':task.name,'role':role,'image':ident,'build_seconds':record['context'][role]['build_seconds']}),flush=True)
        records.append(record)
        (out/'images.json').write_text(json.dumps({'images':records},indent=2)+'\n')
    return records

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--docker-host',default=os.environ.get('DOCKER_HOST'))
    p.add_argument('--docker-config',type=Path)
    p.add_argument('--build-proxy')
    p.add_argument('--output',type=Path,default=ROOT/'runs/prepared')
    build(p.parse_args())
