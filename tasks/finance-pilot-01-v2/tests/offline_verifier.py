"""Finance01 adapter for the shared offline-container rubric bridge v1.

Objective 80 points are computed locally; actual independent judgement covers
M1-M4 only (20 points), with full source/candidate extraction and digest binding.
There are no credentials, canned model responses or answer hash allowlists.
"""
import argparse, hashlib, json, math, os, time, shutil, zipfile, zlib, subprocess, re
from datetime import datetime
from pathlib import Path
from decimal import Decimal, InvalidOperation
import xml.etree.ElementTree as ET
from pypdf import PdfReader
import evaluate as objective

HERE=Path(__file__).resolve().parent
class CandidateFormatError(ValueError): pass
def runtime_health(office):
    poppler=shutil.which('pdftoppm')
    if not office or not Path(office).is_file() or not poppler or not Path(poppler).is_file():raise RuntimeError('declared Office/Poppler runtime missing')
    for binary,args,label in [(office,['--version'],'LibreOffice'),(poppler,['-v'],'pdftoppm')]:
        process=subprocess.run([binary,*args],capture_output=True,text=True,timeout=5)
        version=process.stdout+'\n'+process.stderr
        if process.returncode or label.lower() not in version.lower() or not re.search(r'\d+\.\d+',version):raise RuntimeError(label+' runtime health check failed: exit='+str(process.returncode)+'; output='+version[:200])
def verify_trusted(input_data):
    grader=json.loads((HERE/'grader-hashes.json').read_text())
    if not isinstance(grader,dict) or not grader:raise ValueError('trusted grader manifest invalid')
    for name,digest in grader.items():
        if Path(name).name!=name or objective.sha(HERE/name)!=digest:raise ValueError('trusted grader code/context changed: '+name)
    trusted=json.loads((HERE/'input-hashes.json').read_text())
    if not isinstance(trusted,dict) or not trusted:raise ValueError('trusted input manifest invalid')
    actual={p.name:objective.sha(p) for p in Path(input_data).iterdir() if p.is_file()}
    if actual!=trusted:raise ValueError('missing, extra or changed trusted source/input file')
    office=os.environ.get('SOFFICE') or shutil.which('soffice')
    runtime_health(office)
    return actual
def read_candidate(output):
    """Only exceptions from known candidate format reads become task defects."""
    workbook=Path(output)/'cashflow-review.xlsx';memo=Path(output)/'investment-note.md'
    if not workbook.is_file() or not workbook.stat().st_size:return 'required workbook missing or empty'
    try:
        with zipfile.ZipFile(workbook) as package:
            if package.testzip() is not None:raise CandidateFormatError('candidate XLSX ZIP integrity failure')
            if not {'[Content_Types].xml','xl/workbook.xml','xl/_rels/workbook.xml.rels'}<=set(package.namelist()):raise CandidateFormatError('candidate XLSX required package parts missing')
            root=ET.fromstring(package.read('xl/workbook.xml'));namespace='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
            if root.tag!=namespace+'workbook' or root.find(namespace+'sheets') is None:raise CandidateFormatError('candidate XLSX workbook structure invalid')
            for name in package.namelist():
                if name.endswith(('.xml','.rels')):ET.fromstring(package.read(name))
        objective.Book(workbook)
    except (CandidateFormatError,zipfile.BadZipFile,zlib.error,ET.ParseError,InvalidOperation,KeyError,IndexError,objective.FormulaError) as error:
        return type(error).__name__+': '+str(error)
    if memo.is_file():
        try:memo.read_text(encoding='utf-8')
        except UnicodeDecodeError as error:return 'candidate memo UTF-8 error: '+str(error)
    return None
def serialize(value):
    if isinstance(value,Decimal):return str(value)
    if isinstance(value,Path):return str(value)
    raise TypeError(type(value).__name__)
def canonical_digest(request):return hashlib.sha256(json.dumps(request,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=serialize).encode()).hexdigest()
def make_request(output,input_data,report):
    output=Path(output);input_data=Path(input_data);rubric=json.loads((HERE/'rubric.json').read_text());inputs={};errors=[]
    for p in sorted(input_data.iterdir()):
        if not p.is_file():continue
        if p.suffix.lower()=='.pdf':
            reader=PdfReader(p);inputs[p.name]={'role':'complete_official_annual_report','sha256':objective.sha(p),'page_count':len(reader.pages),'pages':[{'physical_page':i+1,'text':page.extract_text()} for i,page in enumerate(reader.pages)]}
        else:inputs[p.name]={'role':'scope_or_business_handoff_definition','sha256':objective.sha(p),'text':p.read_text(encoding='utf-8')}
    outputs={}
    if (output/'cashflow-review.xlsx').is_file():
        b=objective.Book(output/'cashflow-review.xlsx');index,tables,duplicates=objective.discover(b)
        outputs['cashflow-review.xlsx']={'cells_schema':['sheet','coordinate','type','stored_value_or_cache','formula'], 'cells':[[s,c,v['type'],v.get('value'),v.get('formula')] for (s,c),v in sorted(b.cells.items())],'handoff_tables':tables,'duplicates':duplicates,'formula_evaluation':'objective report contains freshly interpreted formulas and material input perturbations; stored caches here are labeled explicitly and not used alone to award objective credit'}
    if (output/'investment-note.md').is_file():outputs['investment-note.md']={'text':(output/'investment-note.md').read_text(encoding='utf-8')}
    instruction_path=HERE.parent/'instruction.md'
    if not instruction_path.is_file():instruction_path=HERE/'instruction.md'
    criteria=[{'id':c['criterion_id'],'points':c['points'],'object':c['object'],'requirements':c.get('evidence_constrained_rubric'),'acceptable_alternatives':rubric['reasonable_alternatives']} for c in rubric['criteria'] if c['criterion_id'].startswith('M')]
    request={'schema_version':1,'task_id':'finance-pilot-01-v2','instruction':instruction_path.read_text(),'rubric':{'criteria':criteria,'total_points':20,'scoring_scope':'Only professional semantic M1–M4. Objective R1–R6 are already scored out of80 and must not be re-awarded by this judge. Final reward=(earned_objective_80+earned_semantic_20)/100.'},'inputs':inputs,'outputs':outputs,'objective':report,'objective_returncode':0,'extraction_errors':errors,'output_sha256':report['artifact_hashes'],'evidence_context':{'rubric_sha256':objective.sha(HERE/'rubric.json'),'objective_verifier_sha256':objective.sha(HERE/'evaluate.py'),'bridge_sha256':objective.sha(Path(__file__)),'expectations_sha256':objective.sha(HERE/'expectations.json'),'facts_role':'Disclosed historical actuals; the source presents CFO controls, whereas the task requires formula bridge, cross-period contribution and bounded interpretation. No forecasts or added financial scenarios.','semantic_scoring_warning':'Actually read the entire memo and workbook explanations. Correct key terms or correct numeric totals do not prove supported financial reasoning. Evaluate contradictions, causal overclaims, stock-flow confusion, fabricated reconciliation and missing actionable evidence requests.'}}
    # Convert Decimals before sealing so the host computes precisely the same JSON.
    request=json.loads(json.dumps(request,ensure_ascii=False,default=serialize));request['request_sha256']=canonical_digest(request)
    return request

def validate_response(request,response):
    sealed={k:v for k,v in request.items() if k!='request_sha256'}
    if request.get('request_sha256')!=canonical_digest(sealed):raise ValueError('sealed judge request digest changed')
    if response.get('request_sha256')!=request['request_sha256']:raise ValueError('judge response request digest mismatch')
    if response.get('judge_kind') not in ['independent-model-rubric','independent-reviewer-rubric']:raise ValueError('unrecorded independent judge kind')
    identity=response.get('judge_identity')
    if not isinstance(identity,dict) or not identity:raise ValueError('missing actual judge identity')
    if response['judge_kind']=='independent-model-rubric' and (not identity.get('model') or not identity.get('response_id')):raise ValueError('missing actual model/response identity')
    if response['judge_kind']=='independent-reviewer-rubric':
        if not all(isinstance(identity.get(k),str) and identity[k].strip() for k in ['reviewer_id','method']):raise ValueError('missing actual reviewer identity/method')
        if identity['reviewer_id'] in ['/root/harbor_finance_author_01','/root/harbor_finance_package_peer']:raise ValueError('author or package repairer cannot independently score own candidate')
        reviewed_at=identity.get('reviewed_at') or identity.get('executed_at')
        if not isinstance(reviewed_at,str):raise ValueError('missing actual reviewer time')
        try:review_time=datetime.fromisoformat(reviewed_at.replace('Z','+00:00'))
        except ValueError as e:raise ValueError('invalid actual reviewer time') from e
        if review_time.utcoffset() is None:raise ValueError('actual reviewer time must include timezone')
    maxima={r['id']:r['points'] for r in request['rubric']['criteria']};items=response.get('criteria')
    if not isinstance(items,list) or len(items)!=len(maxima):raise ValueError('missing or duplicate semantic criterion')
    ids=[r.get('id') for r in items]
    if len(set(ids))!=len(ids) or set(ids)!=set(maxima):raise ValueError('criterion IDs differ from trusted rubric')
    for r in items:
        score=r.get('score')
        if isinstance(score,bool) or not isinstance(score,(int,float)) or not math.isfinite(score) or not 0<=score<=maxima[r['id']]:raise ValueError('invalid criterion score '+r['id'])
        if not isinstance(r.get('reason'),str) or not r['reason'].strip():raise ValueError('criterion has no evaluation reason')
        if score>0 and (not isinstance(r.get('evidence'),list) or not r['evidence'] or not all(isinstance(e,str) and e.strip() for e in r['evidence'])):raise ValueError('positive credit has no concrete candidate/source evidence')
    return sum(r['score'] for r in items)

def run(output,input_data,logs,wait_seconds,prepare_only=False):
    logs=Path(logs);logs.mkdir(parents=True,exist_ok=True)
    for name in ['reward.txt','reward.json','report.json','judge-request.json']:
        (logs/name).unlink(missing_ok=True)
    report={'status':'verifier_failure','valid':False,'reward':None,'error':'verification incomplete'}
    (logs/'report.json').write_text(json.dumps(report)+'\n')
    try:
        input_hashes=verify_trusted(input_data)
        candidate_defect=read_candidate(output)
        if candidate_defect:
            report={'status':'graded_candidate_defect','valid':True,'reward':0.0,'automatic_points':0,'semantic_points':0,'candidate_defect':candidate_defect,'trusted_input_sha256':input_hashes,'judge_skipped':'Known candidate absence/format defect; deterministic zero'}
        else:
            report=objective.evaluate(output,HERE/'expectations.json')
            if report.get('error'):raise ValueError('objective execution failed: '+report['error'])
            request=make_request(output,input_data,report)
            (logs/'judge-request.json').write_text(json.dumps(request,ensure_ascii=False,indent=2)+'\n')
            report['request_sha256']=request['request_sha256'];report['reward']=None;report['valid']=False
            if prepare_only:report['status']='prepared_pending_independent_judge'
            else:
                deadline=time.monotonic()+wait_seconds;response=None;response_file=logs/'judge-response.json'
                while time.monotonic()<deadline:
                    if response_file.is_file():
                        try:response=json.loads(response_file.read_text())
                        except json.JSONDecodeError:time.sleep(.25);continue
                        if response.get('request_sha256')!=request['request_sha256']:
                            # Stale response belongs to a different trial; wait for
                            # the host to atomically supply this request's review.
                            time.sleep(.5);continue
                        break
                    time.sleep(.5)
                if response is None:raise TimeoutError('Independent semantic judge did not return a current response')
                semantic=validate_response(request,response)
                current_hashes={name:objective.sha(Path(output)/name) for name in ['cashflow-review.xlsx','investment-note.md'] if (Path(output)/name).is_file()}
                if current_hashes!=request['output_sha256']:raise ValueError('candidate bytes changed during independent review')
                report.update(valid=True,semantic_points=semantic,pending_semantic_points=0,reward=round((report['automatic_points']+semantic)/100,6),judge_response=response,semantic_criteria=[{'criterion_id':c['id'],'maximum_points':next(r['points'] for r in request['rubric']['criteria'] if r['id']==c['id']),'points_awarded':c['score'],'status':'adjudicated','reason':c['reason'],'evidence':c['evidence']} for c in response['criteria']])
                report['status']='passed' if report['reward']==1 else 'graded'
    except Exception as e:
        report.update(status='verifier_failure',valid=False,reward=None,error=type(e).__name__+': '+str(e))
    (logs/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=serialize)+'\n')
    if report.get('valid'):
        (logs/'reward.txt').write_text(str(report['reward'])+'\n');(logs/'reward.json').write_text(json.dumps({'reward':report['reward']})+'\n')
    else:
        (logs/'reward.txt').unlink(missing_ok=True);(logs/'reward.json').unlink(missing_ok=True)
    return report

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',default='/workspace/output');p.add_argument('--input-data',default='/workspace/input-data');p.add_argument('--logs',default='/logs/verifier');p.add_argument('--wait-seconds',type=float,default=1800);p.add_argument('--prepare-only',action='store_true');a=p.parse_args()
    r=run(a.output,a.input_data,a.logs,a.wait_seconds,a.prepare_only);print(json.dumps({k:r.get(k) for k in ['status','valid','reward','automatic_points','semantic_points','pending_semantic_points','request_sha256','error']},ensure_ascii=False));return 1 if r['status']=='verifier_failure' else 0
if __name__=='__main__':raise SystemExit(main())
