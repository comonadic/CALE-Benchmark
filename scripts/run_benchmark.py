#!/usr/bin/env python3
"""Run one independent Claude Code attempt per task with native Harbor and host grading."""
import argparse,asyncio,json,os,shlex,shutil,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlparse
from dotenv import dotenv_values
import toml
from harbor.job import Job
from harbor.models.job.config import JobConfig
from harbor.models.task.task import Task
from harbor.models.task.config import HealthcheckConfig
from build_images import tree_hash

ROOT=Path(__file__).resolve().parents[1]

async def run(args):
    started=time.monotonic()
    out=args.output.resolve()
    if out.exists():
        raise ValueError('Use a new output directory for each independent run')
    out.mkdir(parents=True)
    env=dotenv_values(args.env_file)
    api_key=env.get('ANTHROPIC_API_KEY') or os.environ.get('ANTHROPIC_API_KEY')
    base=env.get('ANTHROPIC_BASE_URL') or env.get('RSI_ANTHROPIC_BASE_URL') or os.environ.get('ANTHROPIC_BASE_URL')
    if not api_key or not base:raise ValueError('ANTHROPIC_API_KEY and API base are required')
    os.environ.update({'ANTHROPIC_API_KEY':api_key,'ANTHROPIC_BASE_URL':base,'DOCKER_HOST':args.docker_host,'ANTHROPIC_CUSTOM_HEADERS':'User-Agent: Mozilla/5.0','CLAUDE_CODE_MAX_OUTPUT_TOKENS':'16000'})
    if args.docker_config:os.environ['DOCKER_CONFIG']=str(args.docker_config.resolve())
    records=json.loads(args.images.read_text())['images']
    if args.task:records=[r for r in records if r['task_id'] in args.task]
    if not records:raise ValueError('No matching tasks')
    stage=out/'tasks';stage.mkdir()
    for r in records:
        source=ROOT/'tasks'/r['task_id']
        for role,directory in [('agent','environment'),('verifier','tests')]:
            if tree_hash(source/directory)!=r['context'][role]['tree_sha256']:
                raise ValueError('Prepared image does not match current task context')
        target=stage/r['task_id'];shutil.copytree(source,target)
        cfg=Task(target).config
        cfg.environment.docker_image=r['agent']
        cfg.verifier.environment=cfg.environment.model_copy(deep=True)
        cfg.verifier.environment.docker_image=r['verifier']
        cfg.verifier.environment.cpus=1
        cfg.verifier.environment.memory_mb=2048
        probe="import urllib.request; r=urllib.request.urlopen(urllib.request.Request("+repr(base)+", headers={'User-Agent':'Mozilla/5.0'}),timeout=15); assert 200<=r.status<400"
        cfg.environment.healthcheck=HealthcheckConfig(command='python -c '+shlex.quote(probe),timeout_sec=20,retries=2,interval_sec=2)
        (target/'task.toml').write_text(toml.dumps(cfg.model_dump(mode='json',exclude_none=True)))
    bridges=[];bridge_logs=[]
    try:
        for industry,script,prefix in [('finance','finance_model_bridge.py','finance-pilot-'),('law','host_rubric_bridge.py','legal-pilot-')]:
            selected=[r for r in records if r['task_id'].startswith(prefix)]
            if not selected:continue
            log_path=out/f'{industry}-bridge.log';handle=log_path.open('w');bridge_logs.append(handle)
            cmd=[sys.executable,str(ROOT/'scripts'/script),'--host',args.docker_host,'--task-prefix',prefix,'--allow-external-api','--model',args.model,'--base-url',base,'--env-file',str(args.env_file.resolve()),'--logs',str(out/'judge'/industry),'--duration','21600','--prompt-cache-ttl','off']
            for r in selected:cmd+=['--image',r['verifier']]
            bridges.append(subprocess.Popen(cmd,stdout=handle,stderr=subprocess.STDOUT))
        public_agent_env={
            'ANTHROPIC_CUSTOM_HEADERS':'User-Agent: Mozilla/5.0',
            'CLAUDE_CODE_MAX_OUTPUT_TOKENS':'16000',
            'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC':'1',
            'DISABLE_AUTOUPDATER':'1',
            'API_TIMEOUT_MS':'300000',
        }
        cfg=JobConfig.model_validate({
            'job_name':'claude-opus-5-5','jobs_dir':str(out/'jobs'),'n_attempts':1,'n_concurrent_trials':args.concurrency,'quiet':True,'retry':{'max_retries':0},
            'environment':{'type':'docker','delete':True,'extra_allowed_hosts':[urlparse(base).hostname]},
            'agents':[{'name':'claude-code','model_name':args.model,'override_timeout_sec':args.agent_timeout,'override_setup_timeout_sec':300,'extra_allowed_hosts':[urlparse(base).hostname],
                'env':public_agent_env,'kwargs':{'version':'2.1.296','max_turns':args.max_turns,'reasoning_effort':'medium','disallowed_tools':'Agent,Task,WebSearch,WebFetch'}}],
            'verifier':{'override_timeout_sec':args.verifier_timeout},
            'datasets':[{'path':str(stage)}],
        })
        (out/'run-policy.json').write_text(json.dumps({'started_at':datetime.now(timezone.utc).isoformat(),'model':args.model,'agent':'claude-code','claude_code_version':'2.1.296','concurrency':args.concurrency,'attempts_per_task':1,'max_turns':args.max_turns,'agent_timeout_sec':args.agent_timeout,'verifier_timeout_sec':args.verifier_timeout,'retry_attempts':0,'model_network_preflight':'Heju hostname added to initial agent environment allowlist; HTTP/DNS healthcheck before agent setup','grading_prompt_cache':'off: one unique candidate per task','agent_prompt_cache':'Claude Code default enabled; measure actual usage','task_ids':[r['task_id'] for r in records]},indent=2)+'\n')
        job=await Job.create(cfg)
        result=await job.run()
        (out/'harbor-result.json').write_text(result.model_dump_json(indent=2)+'\n')
        print(json.dumps({'status':'harbor_job_completed','task_count':len(records),'elapsed_seconds':round(time.monotonic()-started,3),'output':str(out)}),flush=True)
    finally:
        for process in bridges:
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:process.kill();process.wait()
        for handle in bridge_logs:handle.close()
        (out/'runner-finished.json').write_text(json.dumps({'finished_at':datetime.now(timezone.utc).isoformat(),'elapsed_seconds':round(time.monotonic()-started,3),'grading_bridge_processes_stopped':all(p.poll() is not None for p in bridges)},indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--env-file',type=Path,required=True)
    p.add_argument('--images',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--docker-host',default=os.environ.get('DOCKER_HOST'),required=not bool(os.environ.get('DOCKER_HOST')))
    p.add_argument('--docker-config',type=Path)
    p.add_argument('--model',default='claude-opus-5-5')
    p.add_argument('--task',action='append')
    p.add_argument('--concurrency',type=int,default=2)
    p.add_argument('--agent-timeout',type=int,default=2400)
    p.add_argument('--verifier-timeout',type=int,default=2100)
    p.add_argument('--max-turns',type=int,default=60)
    asyncio.run(run(p.parse_args()))
