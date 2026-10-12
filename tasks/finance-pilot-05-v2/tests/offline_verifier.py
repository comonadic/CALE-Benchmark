"""Finance05 implementation of offline-container rubric bridge v1.

Objective60 plus independently reviewed40; no network, secret, fabricated review
or reference-output byte whitelist. Any source/code/Office/judge failure has no reward.
"""
import argparse,base64,csv,hashlib,json,math,os,re,shutil,subprocess,tempfile,time,zipfile,zlib
from datetime import datetime
from pathlib import Path
from lxml import etree
from pypdf import PdfReader
from docx import Document
from docx.opc.exceptions import PackageNotFoundError
import objective

HERE=Path(__file__).resolve().parent
NAMES=['rectification-ledger.csv','review-memo.docx']
class CandidateFormatError(ValueError): pass
def runtime_health(office):
    poppler=shutil.which('pdftoppm')
    if not office or not Path(office).is_file() or not poppler or not Path(poppler).is_file():raise RuntimeError('Declared Office/Poppler runtime missing')
    for binary,args,label in [(office,['--version'],'LibreOffice'),(poppler,['-v'],'pdftoppm')]:
        process=subprocess.run([binary,*args],capture_output=True,text=True,timeout=5)
        version=process.stdout+'\n'+process.stderr
        if process.returncode or label.lower() not in version.lower() or not re.search(r'\d+\.\d+',version):raise RuntimeError(label+' runtime health check failed: exit='+str(process.returncode)+'; output='+version[:200])
def canonical(data):return json.dumps(data,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
def digest(data):return hashlib.sha256(canonical(data)).hexdigest()
def verify_inputs(input_data):
    grader=json.loads((HERE/'grader-hashes.json').read_text())
    if not isinstance(grader,dict) or not grader:raise ValueError('Trusted grader manifest invalid')
    for name,expected in grader.items():
        if Path(name).name!=name or objective.sha(HERE/name)!=expected:raise ValueError('Trusted grader code/context changed: '+name)
    trusted=json.loads((HERE/'input-hashes.json').read_text())
    if not isinstance(trusted,dict) or not trusted:raise ValueError('Trusted input manifest invalid')
    actual={p.name:objective.sha(p) for p in input_data.iterdir() if p.is_file()}
    if actual!=trusted:raise ValueError('Missing, extra or changed trusted source/input file')
    return actual
def extract_docx(path):
    ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'};parts=[]
    with zipfile.ZipFile(path) as z:
        if z.testzip() is not None or not {'[Content_Types].xml','_rels/.rels','word/document.xml'}<=set(z.namelist()):raise CandidateFormatError('Candidate DOCX package unreadable')
        for name in z.namelist():
            if not name.startswith('word/') or not name.endswith('.xml') or not any(k in name for k in ['document','header','footer','footnote','endnote']):continue
            root=etree.fromstring(z.read(name));paras=[]
            if name=='word/document.xml' and (root.tag!='{'+ns['w']+'}document' or root.find('w:body',ns) is None):raise CandidateFormatError('Candidate DOCX main document structure invalid')
            for i,p in enumerate(root.xpath('//w:p',namespaces=ns),1):
                current=''.join(p.xpath('.//w:t[not(ancestor::w:del)]/text()',namespaces=ns));deleted=''.join(p.xpath('.//w:delText/text()',namespaces=ns))
                if current or deleted:paras.append({'paragraph':i,'current':current,'deleted_revision_text':deleted,'inside_table':bool(p.xpath('ancestor::w:tc',namespaces=ns))})
            parts.append({'part':name,'paragraphs':paras})
    return {'parts':parts,'current_text_policy':'Only current text earns substantive credit; deleted revision text explicitly separate.'}
def read_candidate(output):
    """Parse candidate formats before grading; never catch Office/code faults."""
    try:objective.load_csv(output/'rectification-ledger.csv')
    except (csv.Error,UnicodeDecodeError,objective.CandidateCSVError) as error:
        return type(error).__name__+': '+str(error)
    try:
        extract_docx(output/'review-memo.docx')
        Document(output/'review-memo.docx')
    except (CandidateFormatError,zipfile.BadZipFile,zlib.error,etree.XMLSyntaxError,PackageNotFoundError,KeyError) as error:
        return type(error).__name__+': '+str(error)
    except ValueError as error:
        if str(error).startswith('file ') and ' is not a Word file, content type is ' in str(error):return 'CandidateFormatError: '+str(error)
        raise
    return None
def render_docx(path,logs,soffice):
    # Render the actual submitted file, without modifying its bytes. A unique
    # Office profile avoids interaction with any other task or desktop instance.
    with tempfile.TemporaryDirectory(prefix='finance05-office-') as tmp:
        tmp=Path(tmp);profile=tmp/'profile';render=tmp/'render';render.mkdir()
        result=subprocess.run([soffice,'-env:UserInstallation='+profile.as_uri(),'--headless','--convert-to','pdf','--outdir',str(render),str(path.resolve())],capture_output=True,text=True,timeout=90)
        (logs/'office-render-log.json').write_text(json.dumps({'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr},ensure_ascii=False,indent=2))
        pdf=render/(path.stem+'.pdf')
        if result.returncode or not pdf.is_file() or not pdf.stat().st_size:raise RuntimeError('Office rendering failed; no valid candidate PDF')
        target=logs/'submitted-memo.pdf';shutil.copyfile(pdf,target)
    reader=PdfReader(target)
    pp=subprocess.run(['pdftoppm','-png','-scale-to','1200',str(target),str(logs/'candidate-memo')],capture_output=True,text=True,timeout=60)
    if pp.returncode:raise RuntimeError('Candidate page image rendering failed: '+pp.stderr)
    images=sorted(logs.glob('candidate-memo-*.png'))
    if len(images)!=len(reader.pages):raise RuntimeError('Candidate page image coverage incomplete')
    return {'rendered_page_count':len(reader.pages),'rendered_pdf_pages':[{'physical_page':i+1,'text':p.extract_text()} for i,p in enumerate(reader.pages)]},images
def make_request(output,input_data,logs,report,soffice):
    inputs={}
    for p in sorted(input_data.iterdir()):
        if p.suffix=='.pdf':
            reader=PdfReader(p);inputs[p.name]={'role':'official public original fixed report/appendix, not independent vouchers or acceptance records','sha256':objective.sha(p),'page_count':len(reader.pages),'pages':[{'physical_page':i+1,'printed_page':None if p.name=='F049.pdf' and i==0 else i if p.name=='F049.pdf' else i+1,'text':page.extract_text()} for i,page in enumerate(reader.pages)]}
        else:inputs[p.name]={'role':'business review definitions/navigation/output handoff schema','sha256':objective.sha(p),'text':p.read_text(encoding='utf-8')}
    outputs={'rectification-ledger.csv':report['csv'],'review-memo.docx':extract_docx(output/'review-memo.docx')}
    rendered,images=render_docx(output/'review-memo.docx',logs,soffice);outputs['review-memo.docx'].update(rendered)
    rubric=json.loads((HERE/'rubric.json').read_text());context=json.loads((HERE/'evidence-context.json').read_text())
    sealed_objective=json.loads(json.dumps(report,ensure_ascii=False))
    request={'schema_version':1,'task_id':'finance-pilot-05-v2','instruction':(HERE/'instruction.md').read_text(),'rubric':{'criteria':rubric['criteria'],'total_points':40,'scoring_scope':'Semantic40 only. Objective60 are already scored with actual candidate assertions. Final reward=(objective60+independent semantic40)/100. Inspect every actual candidate/output before scoring; objective fields do not resolve prose contradictions.'},'inputs':inputs,'outputs':outputs,'objective':sealed_objective,'objective_returncode':0 if report['status']=='passed' else 1,'extraction_errors':[],'output_sha256':{name:objective.sha(output/name) for name in NAMES},'evidence_context':{'verified_source_facts':context,'rubric_sha256':objective.sha(HERE/'rubric.json'),'objective_code_sha256':objective.sha(HERE/'objective.py'),'bridge_code_sha256':objective.sha(Path(__file__)),'input_manifest_sha256':objective.sha(HERE/'input-hashes.json'),'review_scope':'Actual fiscal source citation validity, disclosure boundaries, independent closure and action value. Accept supported different language and evidence plans. Never treat whole-reference-output hash, matching vocabulary or correct numeric cells alone as a professional verdict.','candidate_image_sequence':[{'file':'review-memo.docx','rendered_page':i+1,'purpose':'Actual candidate visual usability'} for i in range(len(images))]},'source_images':[{'media_type':'image/png','data':base64.b64encode(p.read_bytes()).decode('ascii')} for p in images]}
    request['request_sha256']=digest(request)
    return request
def validate_response(request,response):
    if not isinstance(response,dict) or response.get('request_sha256')!=request['request_sha256']:raise ValueError('Response request digest mismatch')
    if response.get('judge_kind') not in ['independent-model-rubric','independent-reviewer-rubric']:raise ValueError('Independent judge kind missing')
    identity=response.get('judge_identity')
    if not isinstance(identity,dict):raise ValueError('Actual judge identity missing')
    if response['judge_kind']=='independent-reviewer-rubric':
        if not all(isinstance(identity.get(k),str) and identity[k].strip() for k in ['reviewer_id','executed_at','method']):raise ValueError('Reviewer identity/time/method incomplete')
        if identity['reviewer_id'] in ['/root/harbor_finance_author_05','harbor_finance_author_05']:raise ValueError('Author cannot act as independent reviewer')
        when=datetime.fromisoformat(identity['executed_at'].replace('Z','+00:00'))
        if when.tzinfo is None:raise ValueError('Reviewer execution timestamp needs timezone')
    elif not all(identity.get(k) for k in ['model','protocol','response_id']):raise ValueError('Actual model response identity incomplete')
    maxima={c['id']:c['points'] for c in request['rubric']['criteria']};items=response.get('criteria')
    if not isinstance(items,list) or any(not isinstance(c,dict) for c in items):raise ValueError('Malformed semantic criteria')
    ids=[c.get('id') for c in items]
    if len(ids)!=len(maxima) or len(set(ids))!=len(ids) or set(ids)!=set(maxima):raise ValueError('Rubric criterion coverage missing/duplicate/extra')
    for c in items:
        score=c.get('score')
        if isinstance(score,bool) or not isinstance(score,(int,float)) or not math.isfinite(score) or not 0<=score<=maxima[c['id']]:raise ValueError('Criterion score out of range: '+c['id'])
        if not isinstance(c.get('reason'),str) or not c['reason'].strip():raise ValueError('Criterion evaluation reason missing')
        if score>0:
            evidence=c.get('evidence')
            if not isinstance(evidence,list) or not evidence or not all(isinstance(v,str) and v.strip() for v in evidence):raise ValueError('Positive credit has no concrete evidence')
            if not any(any(name in v for name in request['outputs']) for v in evidence):raise ValueError('Positive credit has no candidate file evidence anchor')
    return sum(c['score'] for c in items)
def run(output,input_data,logs,wait_seconds=1800,prepare_only=False,soffice=None):
    output=Path(output);input_data=Path(input_data);logs=Path(logs);logs.mkdir(parents=True,exist_ok=True)
    for name in ['reward.txt','reward.json','judge-request.json','report.json','submitted-memo.pdf']:
        (logs/name).unlink(missing_ok=True)
    for p in logs.glob('candidate-memo-*.png'):p.unlink()
    report={'status':'verifier_failure','valid':False,'reward':None,'error':'Verification incomplete'}
    (logs/'report.json').write_text(json.dumps(report)+'\n')
    try:
        input_hashes=verify_inputs(input_data)
        # Even a nop must not mask a broken grader runtime or absent trusted files.
        soffice=soffice or os.environ.get('SOFFICE') or shutil.which('soffice')
        runtime_health(soffice)
        missing=[name for name in NAMES if not (output/name).is_file() or not (output/name).stat().st_size]
        if missing:
            report={'status':'graded','valid':True,'reward':0.0,'missing_required_outputs':missing,'objective_points':0,'semantic_points':0,'judge_skipped':'No complete required submission; deterministic zero','trusted_input_sha256':input_hashes}
        else:
            candidate_defect=read_candidate(output)
            if candidate_defect:
                report={'status':'graded_candidate_defect','valid':True,'reward':0.0,'candidate_defect':candidate_defect,'objective_points':0,'semantic_points':0,'judge_skipped':'Known candidate format defect; deterministic zero','trusted_input_sha256':input_hashes}
                (logs/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
                (logs/'reward.json').write_text(json.dumps({'reward':0.0})+'\n');(logs/'reward.txt').write_text('0.0\n')
                return report
            report=objective.evaluate(output/'rectification-ledger.csv')
            report.update(valid=False,reward=None,status=report['status'])
            request=make_request(output,input_data,logs,report,soffice)
            (logs/'judge-request.json').write_text(json.dumps(request,ensure_ascii=False,indent=2)+'\n')
            report.update(request_sha256=request['request_sha256'],output_sha256=request['output_sha256'],trusted_input_sha256=input_hashes,semantic_points_pending=40)
            if prepare_only:report['status']='prepared_pending_independent_review'
            else:
                deadline=time.monotonic()+wait_seconds;response=None
                while time.monotonic()<deadline:
                    path=logs/'judge-response.json'
                    if path.is_file():
                        response=json.loads(path.read_text(encoding='utf-8'));break
                    time.sleep(.5)
                if response is None:raise TimeoutError('Current independent rubric response missing')
                points=validate_response(request,response)
                if {name:objective.sha(output/name) for name in NAMES}!=request['output_sha256']:raise ValueError('Candidate bytes changed after request was sealed')
                if digest({k:v for k,v in request.items() if k!='request_sha256'})!=request['request_sha256']:raise ValueError('Request content digest failed')
                report.update(status='graded',valid=True,reward=round((report['automatic_points']+points)/100,8),objective_points=report['automatic_points'],semantic_points=points,semantic_points_pending=0,judge_response=response,semantic_criteria=response['criteria'])
    except Exception as error:
        report.update(status='verifier_failure',valid=False,reward=None,error=type(error).__name__+': '+str(error))
    (logs/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    if report.get('valid'):
        (logs/'reward.json').write_text(json.dumps({'reward':report['reward']})+'\n');(logs/'reward.txt').write_text(str(report['reward'])+'\n')
    else:
        (logs/'reward.json').unlink(missing_ok=True);(logs/'reward.txt').unlink(missing_ok=True)
    return report
def main():
    p=argparse.ArgumentParser();p.add_argument('--output',default='/workspace/output');p.add_argument('--input-data',default='/tests/input-data');p.add_argument('--logs',default='/logs/verifier');p.add_argument('--wait-seconds',type=float,default=1800);p.add_argument('--prepare-only',action='store_true');p.add_argument('--soffice');a=p.parse_args()
    r=run(a.output,a.input_data,a.logs,a.wait_seconds,a.prepare_only,a.soffice)
    print(json.dumps({k:r.get(k) for k in ['status','valid','reward','automatic_points','semantic_points','request_sha256','error']},ensure_ascii=False))
    return 1 if r['status']=='verifier_failure' else 0
if __name__=='__main__':raise SystemExit(main())
