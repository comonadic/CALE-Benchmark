#!/usr/bin/env python3
"""Offline objective checks and digest-bound independent professional rubric.

No network, credential, reference-answer whitelist, text similarity or automatic
prose grade. A host reviewer supplies a fresh response for this sealed request.
"""
import argparse, csv, hashlib, json, math, sys, time, zipfile
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET
import objective

HERE = Path(__file__).resolve().parent
REQUIRED = ['risk_ledger.csv', 'funding_results.json', 'action_memo.md']
TASK_ID = 'finance-pilot-04-v2'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')

def save(path, value):
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    temporary.replace(path)

class VisibleHTML(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]; self.skip=0
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'head'): self.skip+=1
    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'head'): self.skip-=1
    def handle_data(self, value):
        if not self.skip and value.strip(): self.parts.append(value.strip())

def extract(path):
    # Every supplied material is extracted in full. HTML navigation is retained;
    # non-visible scripts/styles are not prose or a second rule source.
    result={'sha256':sha(path), 'bytes':path.stat().st_size}
    if path.suffix=='.docx':
        ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        with zipfile.ZipFile(path) as z:
            body=ET.fromstring(z.read('word/document.xml')).find('w:body', ns)
            blocks=[]
            for n, b in enumerate(body):
                texts=[''.join(t.text or '' for t in c.findall('.//w:t',ns)) for c in b.findall('w:tr/w:tc',ns)]
                block={'body_index_zero_based':n, 'type':b.tag.rsplit('}',1)[-1], 'text':''.join(t.text or '' for t in b.findall('.//w:t',ns))}
                if b.tag.endswith('}tbl'):
                    block['rows']=[[''.join(t.text or '' for t in c.findall('.//w:t',ns)) for c in r.findall('w:tc',ns)] for r in b.findall('w:tr',ns)]
                blocks.append(block)
        result['body_blocks']=blocks
    elif path.suffix=='.html':
        p=VisibleHTML(); p.feed(path.read_text(encoding='utf-8')); p.close(); result['visible_text']='\n'.join(p.parts)
    else:
        text=path.read_text(encoding='utf-8-sig'); result['text']=text
        if path.suffix=='.json': result['parsed']=json.loads(text, parse_constant=lambda x: (_ for _ in ()).throw(ValueError('nonfinite JSON '+x)))
        if path.suffix=='.csv': result['rows']=list(csv.DictReader(text.splitlines()))
    return result

def validated_response(req, response, rubric):
    if response.get('request_sha256')!=req['request_sha256']: raise ValueError('judge digest does not bind this request')
    if response.get('judge_kind') not in ('independent-model-rubric','independent-reviewer-rubric'): raise ValueError('not an independent rubric judgement')
    identity=response.get('judge_identity')
    if not isinstance(identity,dict) or not identity: raise ValueError('missing actual judge identity')
    if response['judge_kind']=='independent-model-rubric' and not all(identity.get(k) for k in ['model','protocol','response_id']): raise ValueError('missing model/protocol/response ID')
    if response['judge_kind']=='independent-reviewer-rubric' and not all(identity.get(k) for k in ['reviewer_id','reviewed_at','method']): raise ValueError('missing actual reviewer identity/time/method')
    items=response.get('criteria'); maxima={x['id']:x['points'] for x in rubric['criteria']}
    if not isinstance(items,list) or len(items)!=len(maxima): raise ValueError('missing rubric criteria')
    if len({x.get('id') for x in items})!=len(maxima) or {x.get('id') for x in items}!=set(maxima): raise ValueError('wrong or duplicate rubric IDs')
    for item in items:
        value=item.get('score')
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not 0<=value<=maxima[item['id']]: raise ValueError('out-of-range rubric score')
        if not isinstance(item.get('reason'),str) or not item['reason'].strip(): raise ValueError('missing substantive criterion reason')
        if not isinstance(item.get('evidence'),list) or value>0 and (not item['evidence'] or any(not isinstance(x,str) or not x.strip() for x in item['evidence'])): raise ValueError('positive grade without actual evidence')
    return items

def finalize(req, response, rubric):
    items=validated_response(req,response,rubric); rules={x['id']:x for x in rubric['criteria']}; assertions=req['objective'].get('assertions',[]); errors=req['objective'].get('errors',[])
    scores=[]
    for item in items:
        criterion=item['id']; r=rules[criterion]; subset=[x for x in assertions if x['criterion']==criterion]
        if criterion=='R7':
            ratio=1.0 if not any(x['criterion']=='R7' for x in errors) else 0.0
        else:
            ratio=sum(x['passed'] for x in subset)/len(subset) if subset else 0.0
        ceiling=r['professional_points']+r['objective_points']*ratio
        scores.append({**item,'judge_score':item['score'],'objective_passed':sum(x['passed'] for x in subset),'objective_total':len(subset),'objective_ceiling':ceiling,'score':min(item['score'],ceiling)})
    total=sum(s['score'] for s in scores)
    return {'status':'graded','task_id':TASK_ID,'request_sha256':req['request_sha256'],'output_sha256':req['output_sha256'],'objective':req['objective'],'criteria':scores,'judge':response,'points':total,'max_points':rubric['total_points'],'reward':total/rubric['total_points']}

def run(out, log, wait_seconds):
    log.mkdir(parents=True,exist_ok=True)
    # A stale reward can never mask a failed current verifier.
    for name in ['reward.txt','reward.json','report.json','judge-request.json','judge-response.json']:
        (log/name).unlink(missing_ok=True)
    manifest=json.loads((HERE/'trusted-manifest.json').read_text())
    for name,digest in manifest.items():
        if sha(HERE/name)!=digest: raise ValueError('trusted verifier input changed: '+name)
    rubric=json.loads((HERE/'rubric.json').read_text()); assert sum(x['points'] for x in rubric['criteria'])==rubric['total_points']==100
    def candidate_failure(reason, **details):
        report={'status':'graded-candidate-failure','valid':True,'verifier_failed':False,'task_id':TASK_ID,'reward':0.0,'reason':reason,**details,'criteria':[{'id':x['id'],'score':0,'reason':reason,'evidence':[]} for x in rubric['criteria']]}
        save(log/'report.json',report); save(log/'reward.json',{'reward':0.0}); return report
    missing=[name for name in REQUIRED if not (out/name).is_file() or not (out/name).read_bytes().strip()]
    if missing:
        return candidate_failure('Required candidate work product missing or empty',missing_or_empty=missing)
    # Candidate JSON syntax/encoding defects are completed candidate failures.
    # The narrow catch must not hide source, I/O, objective or judge faults.
    try:
        json.loads((out/'funding_results.json').read_text(encoding='utf-8-sig'))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return candidate_failure('Candidate funding_results.json has invalid JSON syntax or UTF-8 encoding',malformed=['funding_results.json'],candidate_error_type=type(exc).__name__,candidate_error=str(exc))
    inputs={p.name:extract(p) for p in sorted((HERE/'input-data').iterdir()) if p.is_file()}
    outputs={}
    for name in REQUIRED:
        # Required text outputs must be UTF-8. Only candidate decoding defects
        # are completed failures; trusted-source and other execution faults
        # remain outside this narrow boundary.
        try:
            outputs[name]=extract(out/name) if (out/name).is_file() else {'missing':True}
        except UnicodeDecodeError as exc:
            return candidate_failure('Required candidate work product has invalid UTF-8 encoding',malformed=[name],candidate_error_type=type(exc).__name__,candidate_error=str(exc))
    findings=objective.check(out)
    # A completed objective check may correctly find candidate defects; an
    # extraction or script exception cannot be converted to a task reward.
    if not findings.get('completed'): raise ValueError('objective extraction did not complete')
    req={'schema_version':1,'task_id':TASK_ID,'instruction':(HERE/'instruction.md').read_text(),'rubric':rubric,'inputs':inputs,'outputs':outputs,'objective':findings,'objective_returncode':0,'extraction_errors':[],'output_sha256':{n:sha(out/n) for n in REQUIRED if (out/n).is_file()},'evidence_context':json.loads((HERE/'evidence.json').read_text())}
    req['request_sha256']=hashlib.sha256(canonical(req)).hexdigest()
    save(log/'objective.json',findings); save(log/'judge-request.json',req)
    print('JUDGE_REQUEST_READY '+req['request_sha256'],flush=True)
    deadline=time.monotonic()+wait_seconds
    while not (log/'judge-response.json').is_file():
        if time.monotonic()>=deadline: raise TimeoutError('independent host rubric response absent')
        time.sleep(.5)
    response=json.loads((log/'judge-response.json').read_text()); report=finalize(req,response,rubric)
    # Detect output mutation while waiting, rather than attach a judgement to
    # different submitted bytes.
    if req['output_sha256']!={n:sha(out/n) for n in REQUIRED if (out/n).is_file()}: raise ValueError('candidate bytes changed after request sealing')
    save(log/'report.json',report); save(log/'reward.json',{'reward':report['reward']}); return report

def main():
    p=argparse.ArgumentParser(); p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--log-dir',type=Path,required=True);p.add_argument('--judge-timeout',type=float,default=1800);a=p.parse_args()
    try: result=run(a.output_dir,a.log_dir,a.judge_timeout)
    except Exception as exc:
        a.log_dir.mkdir(parents=True,exist_ok=True)
        for name in ['reward.txt','reward.json']: (a.log_dir/name).unlink(missing_ok=True)
        save(a.log_dir/'report.json',{'status':'verifier-invalid','valid':False,'verifier_failed':True,'task_id':TASK_ID,'error_type':type(exc).__name__,'error':str(exc),'reward_emitted':False})
        print('Verifier invalid: '+str(exc),file=sys.stderr);return 1
    print(json.dumps({'status':result['status'],'reward':result['reward']})); return 0

if __name__=='__main__': raise SystemExit(main())
