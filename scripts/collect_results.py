#!/usr/bin/env python3
"""Summarize real Harbor receipts; retain errors and separate agent/judge accounting."""
import argparse,json
from pathlib import Path
from datetime import datetime

FIELDS=['input_tokens','cache_creation_input_tokens','cache_read_input_tokens','output_tokens']

def elapsed(info):
    if not isinstance(info,dict) or not info.get('started_at') or not info.get('finished_at'):return None
    return round((datetime.fromisoformat(info['finished_at'])-datetime.fromisoformat(info['started_at'])).total_seconds(),3)

def events(path):
    if not path.exists():return []
    result=[]
    for line in path.read_text(errors='replace').splitlines():
        try:item=json.loads(line)
        except ValueError:continue
        if isinstance(item,dict):result.append(item)
    return result

def collect(run):
    policy=json.loads((run/'run-policy.json').read_text())
    records=[]
    judges={}
    for path in (run/'judge').glob('*/*/model-response.json'):
        raw=json.loads(path.read_text())
        reqfile=path.parent/'request.json'
        req=json.loads(reqfile.read_text()) if reqfile.exists() else {}
        identity=raw.get('id')
        if identity:
            judges[identity]={'response_id':identity,'task_id':req.get('task_id'),'model':raw.get('model'),'complete':raw.get('stream_complete') is True,'stop_reason':raw.get('stop_reason'),'usage':raw.get('usage'),'raw_sha_source':str(path.relative_to(run))}
    job=run/'jobs/claude-opus-5-5'
    for trial in sorted(job.iterdir()) if job.exists() else []:
        if not trial.is_dir():continue
        resultfile=trial/'result.json'
        result=json.loads(resultfile.read_text()) if resultfile.exists() else {}
        log=events(trial/'agent/claude-code.txt')
        finals=[e for e in log if e.get('type')=='result']
        final=finals[-1] if finals else {}
        messages={}
        for e in log:
            msg=e.get('message')
            if e.get('type')=='assistant' and isinstance(msg,dict) and msg.get('id'):
                messages[msg['id']]=msg
        task_id=trial.name.split('__',1)[0]
        observed_models=sorted({m.get('model') for m in messages.values() if m.get('model')})
        candidate=trial/'artifacts/workspace/output'
        artifactfiles=[str(p.relative_to(candidate)) for p in sorted(candidate.rglob('*')) if p.is_file()] if candidate.exists() else []
        verifier=result.get('verifier_result') or {}
        records.append({'task_id':task_id,'trial_name':trial.name,'completed':bool(result.get('finished_at')),'reward':verifier.get('rewards'),'exception':result.get('exception_info'),
            'seconds':{'total':elapsed(result),'environment_setup':elapsed(result.get('environment_setup')),'agent_setup':elapsed(result.get('agent_setup')),'agent_execution':elapsed(result.get('agent_execution')),'verifier':elapsed(result.get('verifier'))},
            'agent':{'final_result_seen':bool(final),'subtype':final.get('subtype'),'is_error':final.get('is_error'),'num_turns':final.get('num_turns'),'usage':final.get('usage'),'observed_models':observed_models,'response_ids':sorted(messages),'cli_cost_estimate_usd':final.get('total_cost_usd')},
            'candidate_files':artifactfiles,'result_path':str(resultfile.relative_to(run)) if resultfile.exists() else None,'judge_response_ids':[j['response_id'] for j in judges.values() if j['task_id']==task_id]})
    usage={'agent':{},'judge':{}}
    for role,rows in [('agent',[r['agent'] for r in records]),('judge',list(judges.values()))]:
        valid=[r['usage'] for r in rows if isinstance(r.get('usage'),dict)]
        for k in FIELDS:
            usage[role][k]=sum(u.get(k,0) or 0 for u in valid)
        usage[role]['records_with_usage']=len(valid)
        usage[role]['records_without_usage']=len(rows)-len(valid)
    return {'policy':policy,'trials':records,'judge_responses':list(judges.values()),'usage':usage,'completed_trials':sum(r['completed'] for r in records),'scored_trials':sum(r['reward'] is not None for r in records),'invoice_cost_usd':None}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('run',type=Path);p.add_argument('--output',type=Path)
    args=p.parse_args();summary=collect(args.run.resolve())
    if args.output:args.output.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'completed_trials':summary['completed_trials'],'scored_trials':summary['scored_trials'],'trials':[{'task_id':r['task_id'],'reward':r['reward'],'agent_result':r['agent']['subtype'],'seconds':r['seconds']} for r in summary['trials']],'usage':summary['usage']},ensure_ascii=False,indent=2))
