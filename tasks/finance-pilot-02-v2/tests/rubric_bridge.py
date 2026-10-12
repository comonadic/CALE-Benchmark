#!/usr/bin/env python3
"""Offline sealed-request adapter. No credentials,network,reference whitelist or canned professional score."""
import argparse,base64,csv,datetime,hashlib,json,math,os,re,shutil,subprocess,time,traceback,zipfile
from pathlib import Path
from lxml import etree
from pypdf import PdfReader
from evaluate import evaluate,PAGE_MAX
HERE=Path(__file__).resolve().parent
OUTPUT_NAMES=('correction_log.csv','client_note_revised.docx')
AUTHOR_ID='/root/harbor_finance_author_02'
def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def clear_reward(logs):
 for n in ('reward.txt','reward.json','rewards.json'):(logs/n).unlink(missing_ok=True)
def write_reward(logs,r):
 (logs/'reward.txt').write_text(f'{r:.8f}\n');dump(logs/'reward.json',{'reward':r})
def runtime_integrity():
 manifest=json.loads((HERE/'grader-manifest.json').read_text())
 for filename,digest in manifest.items():
  if Path(filename).name!=filename or sha(HERE/filename)!=digest:raise RuntimeError('Trusted grader code/context integrity failure: '+filename)
 source=json.loads((HERE/'source-manifest.json').read_text());inp=Path(os.environ.get('TASK_INPUT_DIR','/workspace/input-data'))
 for filename,digest in source.items():
  if Path(filename).name!=filename or sha(inp/filename)!=digest:raise RuntimeError('Trusted input integrity failure: '+filename)
 office=os.environ.get('OFFICE_BIN') or shutil.which('soffice');poppler=os.environ.get('PDFTOPPM_BIN') or shutil.which('pdftoppm')
 if not office or not Path(office).is_file() or not poppler or not Path(poppler).is_file():raise RuntimeError('Declared LibreOffice/Poppler runtime unavailable')
 for binary,args,label in [(office,['--version'],'LibreOffice'),(poppler,['-v'],'pdftoppm')]:
  process=subprocess.run([binary,*args],capture_output=True,text=True,timeout=5)
  version=process.stdout+'\n'+process.stderr
  if process.returncode or label.lower() not in version.lower() or not re.search(r'\d+\.\d+',version):raise RuntimeError(label+' runtime health check failed: exit='+str(process.returncode)+'; output='+version[:200])
 return inp,office,poppler

def docx_extract(p):
 ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'};parts=[]
 with zipfile.ZipFile(p) as z:
  for name in z.namelist():
   if not name.startswith('word/') or not name.endswith('.xml') or not any(k in name for k in ('document','header','footer','footnote','endnote','comments')):continue
   root=etree.fromstring(z.read(name));paras=[]
   for i,a in enumerate(root.xpath('//w:p',namespaces=ns),1):
    current=''.join(a.xpath('.//w:t[not(ancestor::w:del)]/text()',namespaces=ns));deleted=''.join(a.xpath('.//w:delText/text()',namespaces=ns))
    hidden=''.join(a.xpath('.//w:r[w:rPr/w:vanish or w:rPr/w:webHidden]//w:t/text()',namespaces=ns))
    styles=a.xpath('./w:pPr/w:pStyle/@w:val',namespaces=ns)
    if current or deleted:paras.append({'paragraph':i,'current_text':current,'deleted_revision_text':deleted,'hidden_text':hidden,'style':styles[0] if styles else None})
   tables=[]
   for ti,t in enumerate(root.xpath('//w:tbl',namespaces=ns),1):
    tables.append({'table':ti,'rows':[[{'column':ci,'current_text':'\n'.join(''.join(a.xpath('.//w:t[not(ancestor::w:del)]/text()',namespaces=ns)) for a in cell.xpath('.//w:p',namespaces=ns))} for ci,cell in enumerate(row.xpath('./w:tc',namespaces=ns),1)] for row in t.xpath('./w:tr',namespaces=ns)]})
   parts.append({'part':name,'paragraphs':paras,'tables':tables})
 return {'parts':parts}
def extract(p):
 if p.suffix=='.docx':return docx_extract(p)
 if p.suffix=='.pdf':
  pages=[{'physical_page':i+1,'printed_page':(i-1 if i>=2 else None) if p.name.startswith('F011') else i+1,'text':page.extract_text()} for i,page in enumerate(PdfReader(p).pages)]
  return {'pages':pages}
 text=p.read_text(encoding='utf-8-sig')
 if p.suffix=='.csv':return {'text':text,'rows':list(csv.DictReader(text.splitlines()))}
 return {'text':text}
def render(output,logs,office,poppler):
 target=logs/'rendered-candidate';target.mkdir(exist_ok=True)
 profile=logs/'lo-profile';profile.mkdir(exist_ok=True)
 env=os.environ.copy()
 r=subprocess.run([office,'--headless','-env:UserInstallation='+profile.resolve().as_uri(),'--convert-to','pdf','--outdir',str(target),str(output/'client_note_revised.docx')],capture_output=True,text=True,timeout=90,env=env)
 dump(logs/'render-process.json',{'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
 pdf=target/'client_note_revised.pdf'
 if r.returncode or not pdf.is_file() or pdf.stat().st_size<100:raise RuntimeError('LibreOffice candidate rendering failed')
 r=subprocess.run([poppler,'-png','-scale-to','1200',str(pdf),str(target/'client-note-page')],capture_output=True,timeout=90)
 if r.returncode:raise RuntimeError('Poppler candidate rendering failed')
 pages=sorted(target.glob('client-note-page-*.png'))
 if not pages:raise RuntimeError('Candidate rendering returned no page images')
 return [{'name':f'client_note_revised.docx renderedpage{i+1}','media_type':'image/png','data':base64.b64encode(p.read_bytes()).decode()} for i,p in enumerate(pages)]
def source_images(inp,logs,poppler):
 images=[];dest=logs/'source-images';dest.mkdir(exist_ok=True)
 for name,a,b in [('F013_CCA_2026-06.pdf',5,6),('F011_AT1_fourth_prospectus.pdf',149,149)]:
  prefix=dest/(Path(name).stem+'-page')
  r=subprocess.run([poppler,'-f',str(a),'-l',str(b),'-png','-scale-to','1200',str(inp/name),str(prefix)],capture_output=True,timeout=60)
  files=sorted(dest.glob(prefix.name+'-*.png'))
  if r.returncode or len(files)!=b-a+1:raise RuntimeError('Trusted source image rendering failed: '+name)
  images.extend({'name':name+' physicalpage'+str(a+i),'media_type':'image/png','data':base64.b64encode(p.read_bytes()).decode()} for i,p in enumerate(files))
 return images

def create_request(output,logs,inp,office,poppler,obj):
 hashes={n:sha(output/n) for n in OUTPUT_NAMES};outputs={n:extract(output/n) for n in OUTPUT_NAMES}
 context=json.loads((HERE/'evidence-context.json').read_text());inputs={}
 for name in sorted(json.loads((HERE/'source-manifest.json').read_text())):
  p=inp/name;inputs[name]={'sha256':sha(p),'role':context['source_roles'][name],**extract(p)}
 request={'schema_version':1,'task_id':'finance-pilot-02-v2','instruction':(HERE/'instruction-context.md').read_text(),'rubric':json.loads((HERE/'rubric.json').read_text()),'inputs':inputs,'outputs':outputs,'objective':obj,'objective_returncode':0,'extraction_errors':[],'output_sha256':hashes,'evidence_context':context,'source_images':render(output,logs,office,poppler)+source_images(inp,logs,poppler)}
 # Neither output paths nor case labels enter the professional request.
 request['request_sha256']=hashlib.sha256(canonical(request)).hexdigest()
 return request

def validate_request(req):
 d={k:v for k,v in req.items() if k!='request_sha256'}
 if req.get('request_sha256')!=hashlib.sha256(canonical(d)).hexdigest():raise ValueError('Sealed request digest changed')
 if req.get('schema_version')!=1 or req.get('task_id')!='finance-pilot-02-v2':raise ValueError('Wrong request task/schema')
 if set(req.get('outputs',{}))!=set(OUTPUT_NAMES):raise ValueError('Request output coverage invalid')

def validate_response(req,response):
 validate_request(req)
 if response.get('request_sha256')!=req['request_sha256']:raise ValueError('Independent review response digest mismatch')
 kind=response.get('judge_kind');identity=response.get('judge_identity')
 if kind not in ('independent-model-rubric','independent-reviewer-rubric') or not isinstance(identity,dict):raise ValueError('Unsupported independent judge kind/identity')
 if kind=='independent-reviewer-rubric':
  if not identity.get('reviewer_id') or not (identity.get('reviewed_at') or identity.get('executed_at')) or not identity.get('method'):raise ValueError('Actual independent reviewer identity incomplete')
  if identity['reviewer_id']==AUTHOR_ID:raise ValueError('Author cannot independently score own candidate')
 else:
  if not all(identity.get(k) for k in ('model','protocol','response_id','usage')):raise ValueError('Actual model response identity/usage incomplete')
 maxima={c['id']:c['points'] for c in req['rubric']['criteria']};items=response.get('criteria')
 if not isinstance(items,list) or len(items)!=len(maxima) or {x.get('id') for x in items}!=set(maxima):raise ValueError('Incomplete or duplicate rubric criteria')
 for x in items:
  s=x.get('score')
  if isinstance(s,bool) or not isinstance(s,(int,float)) or not math.isfinite(s) or not 0<=s<=maxima[x['id']]:raise ValueError('Criterion score outside finite range')
  if not isinstance(x.get('reason'),str) or not x['reason'].strip():raise ValueError('Substantive assessment reason absent')
  ev=x.get('evidence')
  if not isinstance(ev,list) or not all(isinstance(z,str) and z.strip() for z in ev):raise ValueError('Criterion evidence invalid')
  if s>0:
   if not ev or not any(n in '\n'.join(ev) for n in OUTPUT_NAMES):raise ValueError('Positive score requires actual candidate filename/location evidence')
   input_anchors=list(req['inputs'])+['F011','F013','F014']
   if not any(n in '\n'.join(ev) for n in input_anchors):raise ValueError('Positive score requires actual input/source evidence')
 if not isinstance(response.get('critical_error'),bool):raise ValueError('Reviewer must explicitly assess critical_error as boolean')
 return items

def aggregate(req,response):
 items=validate_response(req,response);upper={c['criterion_id']:c['points_awarded'] for c in req['objective']['criteria'] if c['criterion_id'].startswith('C')};scores=[]
 for item in items:
  c=item['id'];earned=min(item['score'],upper[c]) if c in upper else item['score']
  scores.append({'id':c,'objective_upper_bound':upper.get(c),'judge_score':item['score'],'score':earned,'reason':item['reason'],'evidence':item['evidence']})
 before=sum(x['score'] for x in scores);cap=bool(req['objective']['critical_error_check_ids']) or response.get('critical_error',False);points=min(before,59) if cap else before
 return {'valid':True,'verifier_failed':False,'grading_complete':True,'status':'completed','request_sha256':req['request_sha256'],'output_sha256':req['output_sha256'],'objective_points':req['objective']['automatic_points'],'typed_points_after_independent_support_review':sum(x['score'] for x in scores if x['id'].startswith('C')),'independent_review_points':sum(x['score'] for x in scores if x['id'].startswith('DOCX')),'points_before_cap':before,'points':points,'reward':round(points/100,8),'applied_cap':59 if cap else None,'judge_identity':response['judge_identity'],'judge_kind':response['judge_kind'],'assertions':scores,'professional_evaluation':response,'objective':req['objective']}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output-dir',default='/workspace/output');ap.add_argument('--log-dir',default='/logs/verifier');ap.add_argument('--prepare-only',action='store_true');ap.add_argument('--finalize-only',action='store_true');a=ap.parse_args();output=Path(a.output_dir);logs=Path(a.log_dir);logs.mkdir(parents=True,exist_ok=True);clear_reward(logs)
 try:
  inp,office,poppler=runtime_integrity()
  if a.finalize_only:
   req=json.loads((logs/'judge-request.json').read_text());validate_request(req)
  else:
   obj=evaluate(output);obj.pop('reward',None);obj.pop('objective_fraction',None);obj['scope']='Typed values/roles and locator admissibility only; actual citation support and all free prose require independent review.';dump(logs/'objective-report.json',obj);dump(logs/'criterion_report.json',obj)
   # Normal absence or unreadable required artifacts are genuine candidate failures.
   if any(not (output/n).is_file() for n in OUTPUT_NAMES) or not obj['docx_precheck']['passed'] or obj['schema_errors']:
    report={'valid':True,'verifier_failed':False,'grading_complete':True,'status':'candidate_failure','reason':'Required candidate artifacts absent,unreadable or invalid audit schema','objective':obj,'points':0,'reward':0,'judge_status':'not_needed_for_artifact_prerequisite_failure'};dump(logs/'report.json',report);dump(logs/'criterion_report.json',report);write_reward(logs,0);return 0
   req=create_request(output,logs,inp,office,poppler,obj);dump(logs/'judge-request.json',req)
  if any(sha(output/n)!=h for n,h in req['output_sha256'].items()):raise ValueError('Candidate bytes changed since request sealing')
  if any(sha(inp/n)!=v['sha256'] for n,v in req['inputs'].items()):raise ValueError('Trusted input bytes changed since request sealing')
  if a.prepare_only:
   dump(logs/'report.json',{'valid':False,'verifier_failed':False,'grading_complete':False,'status':'prepared','request_sha256':req['request_sha256'],'pending_criteria':[c['id'] for c in req['rubric']['criteria']],'objective_points':req['objective']['automatic_points'],'note':'Canonical request prepared,noindependentassessment andno finalreward'});print('FINANCE_JUDGE_REQUEST_READY '+req['request_sha256'],flush=True);return 0
  print('FINANCE_JUDGE_REQUEST_READY '+req['request_sha256'],flush=True)
  deadline=time.monotonic()+float(os.environ.get('RUBRIC_WAIT_SEC','1800'));responsepath=logs/'judge-response.json'
  while not responsepath.is_file():
   if time.monotonic()>deadline:raise TimeoutError('Independent professional reviewer response missing')
   time.sleep(.25)
  response=json.loads(responsepath.read_text());report=aggregate(req,response)
  if any(sha(output/n)!=h for n,h in req['output_sha256'].items()):raise ValueError('Candidate changed during independent review')
  report['executed_at_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();dump(logs/'report.json',report);dump(logs/'criterion_report.json',report);write_reward(logs,report['reward']);print(json.dumps({'status':'completed','reward':report['reward'],'judge_kind':report['judge_kind']}));return 0
 except Exception as e:
  clear_reward(logs);dump(logs/'report.json',{'valid':False,'verifier_failed':True,'grading_complete':False,'status':'invalid','error_type':type(e).__name__,'error':str(e),'scope':'gradercode/trustedsource/extraction/render/judge failure,not a fabricated taskscore','traceback':traceback.format_exc()});print(json.dumps({'status':'invalid','error_type':type(e).__name__}));return 2
if __name__=='__main__':raise SystemExit(main())
