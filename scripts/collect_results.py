#!/usr/bin/env python3
"""Summarize real Harbor receipts; retain errors and separate agent/judge accounting."""
import argparse,json,hashlib
from pathlib import Path
from datetime import datetime

FIELDS=['input_tokens','cache_creation_input_tokens','cache_read_input_tokens','output_tokens']

def elapsed(info):
    if not isinstance(info,dict) or not info.get('started_at') or not info.get('finished_at'):return None
    return round((datetime.fromisoformat(info['finished_at'].replace('Z','+00:00'))-datetime.fromisoformat(info['started_at'].replace('Z','+00:00'))).total_seconds(),3)

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
    stopfile=run/'user-stop.json'
    user_stop=json.loads(stopfile.read_text()) if stopfile.exists() else None
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
    job_config=json.loads((job/'config.json').read_text()) if (job/'config.json').exists() else {}
    runtime_agents=[{k:a.get(k) for k in ['name','model_name','override_timeout_sec','kwargs']} for a in job_config.get('agents',[])]
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
        candidate=trial/'artifacts/main/workspace/output'
        if not candidate.exists():candidate=trial/'artifacts/workspace/output'
        artifactfiles=[str(p.relative_to(candidate)) for p in sorted(candidate.rglob('*')) if p.is_file()] if candidate.exists() else []
        verifier=result.get('verifier_result') or {}
        gradefile=trial/'verifier/report.json'
        grade=json.loads(gradefile.read_text()) if gradefile.exists() else {}
        objective=grade.get('objective') or {}
        assertions=objective.get('assertions',objective.get('checks',[]))
        criteria=grade.get('criteria',(grade.get('professional_evaluation') or {}).get('criteria',[]))
        maxima={c.get('id'):c.get('max_points') for c in grade.get('assertions',[]) if isinstance(c,dict)}
        scoring_details={'status':grade.get('status','graded' if grade.get('valid') else None),'mode':grade.get('mode'),'points':grade.get('points'),'max_points':grade.get('max_points'),
            'request_sha256':grade.get('request_sha256'),'output_sha256':grade.get('output_sha256'),'report_sha256':hashlib.sha256(gradefile.read_bytes()).hexdigest(),
            'objective_status':objective.get('status'),'objective_assertions':len(assertions),'objective_failed':[{'criterion':a.get('criterion'),'object':a.get('object',a.get('id'))} for a in assertions if a.get('passed') is False],
            'criteria':[{'id':c.get('id'),'score':c.get('score'),'max_points':c.get('max_points',maxima.get(c.get('id'))),'judge_score':c.get('judge_score'),'objective_ceiling':c.get('objective_ceiling')} for c in criteria if isinstance(c,dict)]} if grade else None
        records.append({'task_id':task_id,'trial_name':trial.name,'completed':bool(result.get('finished_at')),'reward':verifier.get('rewards'),'exception':result.get('exception_info'),
            'started_at':result.get('started_at'),'finished_at':result.get('finished_at'),
            'scoring_details':scoring_details,
            'receipt_sha256':{str(p.relative_to(trial)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [resultfile,trial/'agent/claude-code.txt'] if p.exists()},
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
    transport=[]
    for q in sorted((run/'model-transport').glob('*.json')):
        item=json.loads(q.read_text())
        if item.get('route') in ['/v1/messages','/messages']:transport.append(item)
    known={item['response_id']:item for item in transport if item.get('response_id') and isinstance(item.get('usage'),dict)}
    for trial in records:
        source=json.loads((run/trial['result_path']).read_text()) if trial['result_path'] else {}
        timing=source.get('agent_execution') or {}
        if timing.get('started_at') and timing.get('finished_at'):
            start=datetime.fromisoformat(timing['started_at'].replace('Z','+00:00')).timestamp()
            end=datetime.fromisoformat(timing['finished_at'].replace('Z','+00:00')).timestamp()
            calls=[r for r in transport if start<=r.get('started_at_unix',0)<=end]
            hashes=[r['request_sha256'] for r in calls if r.get('request_sha256')]
            trial['agent_transport_summary']={'http_requests':len(calls),'incomplete_responses':sum(r.get('stream_complete') is not True for r in calls),
                'requests_without_usage':sum(not isinstance(r.get('usage'),dict) for r in calls),
                'identical_body_extra_requests':len(hashes)-len(set(hashes)),
                'maximum_request_seconds':max((r.get('elapsed_seconds',0) for r in calls),default=None)}
        else:trial['agent_transport_summary']=None
    usage['agent_provider']={k:sum((item['usage'].get(k,0) or 0) for item in known.values()) for k in FIELDS}
    usage['agent_provider'].update(records_with_usage=len(known),requests_without_usage=sum(not isinstance(item.get('usage'),dict) for item in transport),stream_incomplete=sum(item.get('stream_complete') is not True for item in transport))
    return {'policy':policy,'user_stop':user_stop,'runtime_agents':runtime_agents,'trials':records,'judge_responses':list(judges.values()),'agent_transport':transport,'usage':usage,'completed_trials':sum(r['completed'] for r in records),'scored_trials':sum(r['reward'] is not None for r in records),'invoice_cost_usd':None}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('run',type=Path);p.add_argument('--output',type=Path)
    args=p.parse_args();summary=collect(args.run.resolve())
    if args.output:args.output.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'completed_trials':summary['completed_trials'],'scored_trials':summary['scored_trials'],'trials':[{'task_id':r['task_id'],'reward':r['reward'],'agent_result':r['agent']['subtype'],'seconds':r['seconds']} for r in summary['trials']],'usage':summary['usage']},ensure_ascii=False,indent=2))
