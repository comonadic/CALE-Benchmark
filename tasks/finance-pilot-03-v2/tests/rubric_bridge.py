"""Offline-container side of shared rubric bridge v1; no network or credentials."""
import argparse,base64,hashlib,json,math,os,subprocess,time,traceback,zipfile
from pathlib import Path
from lxml import etree
import openpyxl
from pypdf import PdfReader

def canonical(obj):return json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def clear_reward(logs):
    for name in ['reward.txt','reward.json']:(logs/name).unlink(missing_ok=True)
def validate_candidate_binding(req,output):
    if any(sha(output/name)!=digest for name,digest in req['output_sha256'].items()):raise ValueError('Candidate bytes changed after request sealing')
def xlsx_extract(path):
    wb=openpyxl.load_workbook(path,data_only=False);cache=openpyxl.load_workbook(path,data_only=True)
    sheets=[]
    for sh in wb:
        cells=[]
        for row in sh:
            for c in row:
                if c.value is not None:
                    cells.append({'coordinate':c.coordinate,'value':c.value if c.data_type!='f' else None,'formula':c.value if c.data_type=='f' else None,'saved_cache':cache[sh.title][c.coordinate].value,'number_format':c.number_format,'font':{'name':c.font.name,'size':c.font.sz},'alignment':{'wrap_text':c.alignment.wrap_text,'horizontal':c.alignment.horizontal}})
        sheets.append({'name':sh.title,'state':sh.sheet_state,'cells':cells,'column_dimensions':{k:{'width':v.width,'hidden':v.hidden} for k,v in sh.column_dimensions.items()},'row_dimensions':{str(k):{'height':v.height,'hidden':v.hidden} for k,v in sh.row_dimensions.items()},'merged_ranges':[str(x) for x in sh.merged_cells.ranges]})
    return {'sheets':sheets,'defined_names':{k:v.attr_text for k,v in wb.defined_names.items()}}
def docx_extract(path):
    ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'};parts=[]
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            if not name.startswith('word/') or not name.endswith('.xml') or ('document' not in name and 'header' not in name and 'footer' not in name and 'footnote' not in name and 'endnote' not in name):continue
            root=etree.fromstring(z.read(name));paragraphs=[]
            for p in root.xpath('//w:p',namespaces=ns):
                current=''.join(p.xpath('.//w:t[not(ancestor::w:del)]/text()',namespaces=ns))
                deleted=''.join(p.xpath('.//w:delText/text()',namespaces=ns))
                if current or deleted:paragraphs.append({'current':current,'deleted_revision_text':deleted})
            parts.append({'part':name,'paragraphs':paragraphs})
    return {'parts':parts}
def create_request(output,logs,tests):
    context=json.loads((tests/'judge-context.json').read_text())
    obj=json.loads((logs/'criterion-results.json').read_text())
    if obj.get('error'):raise RuntimeError('Objective verifier execution failed: '+obj['error'])
    outputs={};hashes={}
    for name in ['distribution-model.xlsx','distribution-note.docx']:
        p=output/name;hashes[name]=sha(p)
        outputs[name]=xlsx_extract(p) if p.suffix=='.xlsx' else docx_extract(p)
    inputdir=Path(os.environ.get('TASK_INPUT_DIR','/workspace/input-data'))
    inputs={}
    for p in sorted(inputdir.iterdir()):
        if p.suffix=='.pdf':inputs[p.name]={'sha256':sha(p),'role':'official fixed annual report','pages':[{'physical_page':i+1,'text':page.extract_text()} for i,page in enumerate(PdfReader(p).pages)]}
        else:inputs[p.name]={'sha256':sha(p),'role':'search extract' if p.suffix=='.txt' else 'financial discussion assumptions','text':p.read_text()}
    request={'schema_version':1,'task_id':'finance-pilot-03-v2','instruction':(tests/'instruction-context.md').read_text(),'rubric':context['rubric'],'inputs':inputs,'outputs':outputs,'objective':obj,'objective_returncode':0 if obj['status']=='passed' else 1,'extraction_errors':[],'output_sha256':hashes,'evidence_context':context['evidence_context'],'score_contract':'Review all seven full rubric criteria. Objective evidence is a technical upper bound, not semantic credit. Final criterion = min(objective technical points upper bound + that criterion professional maximum, actual independent criterion score); sum / 100. Status meaning must be assessed from each actual recalculated decision cell and its case values, not words elsewhere. No professional points are prefilled or added a second time.'}
    pdf=logs/'submitted-note.pdf'
    if pdf.exists():
        imageprefix=logs/'candidate-note'
        p=subprocess.run(['pdftoppm','-png','-scale-to','1200',str(pdf),str(imageprefix)],capture_output=True,timeout=45)
        if p.returncode:raise RuntimeError('Candidate DOCX image rendering failed')
        images=sorted(logs.glob('candidate-note-*.png'))
        request['source_images']=[{'media_type':'image/png','data':base64.b64encode(p.read_bytes()).decode()} for p in images]
        request['evidence_context']['image_sequence']=[{'file':'distribution-note.docx','physical_rendered_page':i+1,'purpose':'actual candidate visual review'} for i in range(len(images))]
    request=json.loads(json.dumps(request,ensure_ascii=False,default=lambda x:x.isoformat() if hasattr(x,'isoformat') else str(x)))
    request['request_sha256']=hashlib.sha256(canonical(request)).hexdigest()
    return request
def validate_response(req,response):
    if not isinstance(response,dict):raise ValueError('Judge response must be an object')
    sealed=dict(req);digest=sealed.pop('request_sha256',None)
    if digest!=hashlib.sha256(canonical(sealed)).hexdigest():raise ValueError('Sealed judge request digest is invalid')
    if response.get('request_sha256')!=req['request_sha256']:raise ValueError('Judge request digest mismatch')
    if response.get('judge_kind') not in ['independent-model-rubric','independent-reviewer-rubric']:raise ValueError('Judge kind is not independent rubric')
    identity=response.get('judge_identity')
    if not isinstance(identity,dict):raise ValueError('Incomplete actual judge identity')
    if response['judge_kind']=='independent-model-rubric':
        if not identity.get('model') or not identity.get('protocol') or not identity.get('response_id'):raise ValueError('Incomplete actual model judge identity')
    elif not identity.get('reviewer_id') or not identity.get('executed_at') or not identity.get('method'):
        raise ValueError('Incomplete actual independent reviewer identity')
    maximum={c['id']:c['points'] for c in req['rubric']['criteria']};items=response.get('criteria')
    if not isinstance(items,list) or not all(isinstance(x,dict) for x in items) or len(items)!=len(maximum) or {x.get('id') for x in items}!=set(maximum):raise ValueError('Judge rubric criterion coverage incomplete or duplicated')
    for x in items:
        score=x.get('score')
        if isinstance(score,bool) or not isinstance(score,(int,float)) or not math.isfinite(score) or not 0<=score<=maximum[x['id']]:raise ValueError('Judge score outside rubric range')
        if not isinstance(x.get('reason'),str) or not x['reason'].strip():raise ValueError('Judge reason missing')
        if score>0 and (not isinstance(x.get('evidence'),list) or not x['evidence'] or not all(isinstance(v,str) and v.strip() for v in x['evidence'])):raise ValueError('Positive judge credit without concrete evidence')
        if score>0:
            evidence='\n'.join(x['evidence'])
            anchors=list(req['outputs'])+[s['name'] for s in req['outputs']['distribution-model.xlsx']['sheets']]
            if not any(anchor in evidence for anchor in anchors):raise ValueError('Positive evidence has no actual candidate file/sheet location')
    return sum(x['score'] for x in items)
def aggregate(req,response):
    raw=validate_response(req,response)
    rubric=req['rubric'];obj=req['objective']
    if rubric['total_points']!=100 or obj['automatic_points_available']!=80 or rubric['professional_review_points']!=20:raise ValueError('Unexpected rubric coverage')
    if obj.get('error') or obj.get('verifier_failed'):raise ValueError('Objective verifier execution failed')
    criteria={c['id']:c for c in rubric['criteria']};groups=obj['criterion_summary'];scores=[]
    for reviewed in response['criteria']:
        criterion=criteria[reviewed['id']];technical=criterion['automatic_points'];professional=criterion['manual_points']
        if technical:
            group=groups.get(criterion['id'])
            if not isinstance(group,dict) or group.get('automatic_points_available')!=technical:raise ValueError('Objective criterion coverage mismatch')
            earned=group.get('automatic_points_earned')
            if isinstance(earned,bool) or not isinstance(earned,(int,float)) or not math.isfinite(earned) or not 0<=earned<=technical:raise ValueError('Invalid objective technical upper bound')
        else:earned=0
        if technical+professional!=criterion['points']:raise ValueError('Criterion points split mismatch')
        upper=earned+professional;final=min(upper,reviewed['score'])
        scores.append({**reviewed,'objective_technical_points_upper_bound':earned,'professional_points_available':professional,'final_criterion_upper_bound':upper,'final_score':final,'settlement':'min(final_criterion_upper_bound, independent_judge_score)'})
    total=sum(x['final_score'] for x in scores)
    return {'status':'completed','grading_complete':True,'independent_judge_status':'passed','professional_judge_status':'passed','request_sha256':req['request_sha256'],'objective_technical_points_upper_bound':sum(x['objective_technical_points_upper_bound'] for x in scores),'professional_points_available':20,'professional_points':None,'independent_rubric_points':raw,'total_points_earned':total,'total_points_available':100,'criterion_scores':scores,'reward':total/100,'professional_judge_response':response,'objective':obj,'reward_scope':'100-point full independent rubric capped by per-criterion native technical upper bounds; no automatic professional credit'}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output-dir',default='/workspace/output');ap.add_argument('--log-dir',default='/logs/verifier');ap.add_argument('--prepare-only',action='store_true');args=ap.parse_args()
    output=Path(args.output_dir);logs=Path(args.log_dir);tests=Path(__file__).parent;logs.mkdir(parents=True,exist_ok=True)
    clear_reward(logs)
    report={'status':'failed','reward_scope':'full100-point independent rubric bounded by objective evidence','professional_judge_status':'not_run','independent_judge_status':'not_run','professional_points':None,'grading_complete':False}
    try:
        objective=json.loads((logs/'criterion-results.json').read_text())
        if objective.get('status')=='invalid_submission':
            report.update(status='completed',submission_status='invalid_submission',grading_complete=True,reward=0,total_points_earned=0,total_points_available=100,candidate_failure_reason=objective['candidate_failure_reason'],objective=objective,professional_judge_status='not_required_for_invalid_submission',independent_judge_status='not_required_for_invalid_submission',criterion_scores=[{'id':c['id'],'final_score':0,'reason':'Public business handoff contract not satisfied'} for c in json.loads((tests/'judge-context.json').read_text())['rubric']['criteria']])
            (logs/'reward.txt').write_text('0\n');(logs/'reward.json').write_text(json.dumps({'reward':0},indent=2))
            return 0
        req=create_request(output,logs,tests);(logs/'judge-request.json').write_text(json.dumps(req,ensure_ascii=False,indent=2,default=str))
        if args.prepare_only:
            report.update(status='prepared',request_sha256=req['request_sha256'],pending_criteria=[c['id'] for c in req['rubric']['criteria']],objective_technical_points_upper_bound=req['objective']['objective_technical_points_upper_bound'])
            print(json.dumps({'status':'prepared','request_sha256':req['request_sha256']}));return 0
        # A stale response cannot bind: submitted files and objective findings seal a fresh canonical request.
        deadline=time.monotonic()+float(os.environ.get('RUBRIC_WAIT_SEC','1800'))
        while time.monotonic()<deadline:
            responsepath=logs/'judge-response.json'
            if responsepath.exists():
                response=json.loads(responsepath.read_text());validate_response(req,response);break
            time.sleep(.5)
        else:raise TimeoutError('Independent full rubric response was not supplied')
        validate_candidate_binding(req,output)
        report=aggregate(req,response);reward=report['reward']
        (logs/'reward.txt').write_text(f'{reward:.8f}\n');(logs/'reward.json').write_text(json.dumps({'reward':reward},indent=2))
    except Exception as exc:
        report.update(status='invalid',error=str(exc),traceback=traceback.format_exc(),professional_judge_status='failed',independent_judge_status='failed',grading_complete=False)
        # Harbor reads reward files regardless of exit status. Do not turn grader failure into task0.
        clear_reward(logs)
        report['verifier_failed']=True
    finally:
        (logs/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str))
    return 0 if report['status']=='completed' else 1
if __name__=='__main__':raise SystemExit(main())
