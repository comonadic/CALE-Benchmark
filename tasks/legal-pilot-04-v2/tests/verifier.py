#!/usr/bin/env python3
"""Native verifier: objective checks plus an independently executed rubric judge.
No reference matching, credential, model, or source-answer text is embedded here.
A host judge reads the sealed request and deposits its scored response at runtime.
"""
from pathlib import Path
import json,sys,subprocess,hashlib,time,os,datetime,zipfile,csv,base64,shutil
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parent
OUT=Path(os.getenv('LEGAL_OUTPUT_DIR','/workspace/output'))
INP=Path(os.getenv('LEGAL_INPUT_DIR','/workspace/input-data'))
LOG=Path(os.getenv('LEGAL_LOG_DIR','/logs/verifier'));LOG.mkdir(parents=True,exist_ok=True)

def dump(name,value):
 p=LOG/name; tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');tmp.replace(p)

def check_ooxml(p,required):
 with zipfile.ZipFile(p) as z:
  bad=z.testzip()
  if bad:raise ValueError('Invalid ZIP member: '+bad)
  if required not in z.namelist():raise ValueError('Missing OOXML member: '+required)
  for name in z.namelist():
   if name.endswith(('.xml','.rels')):ET.fromstring(z.read(name))

def extract(p):
 if p.suffix.lower()=='.docx':
  check_ooxml(p,'word/document.xml')
  with zipfile.ZipFile(p) as z:
   xml=ET.fromstring(z.read('word/document.xml'))
   ns='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
   def paragraph(n):
    current=[];deleted=[]
    def walk(node,in_deleted=False):
     in_deleted=in_deleted or node.tag==ns+'del'
     if node.tag in {ns+'t',ns+'delText'} and node.text:
      (deleted if in_deleted else current).append(node.text)
     for child in node:walk(child,in_deleted)
    walk(n)
    return {'current_text':''.join(current),'deleted_revision_text':''.join(deleted)}
   return {'type':'docx','paragraphs':[dict(paragraph=n+1,**paragraph(v)) for n,v in enumerate(xml.iter(ns+'p'))]}
 if p.suffix.lower()=='.xlsx':
  # Reject corrupt candidate bytes before invoking a native engine. Missing
  # parsing/runtime dependencies for a well-formed workbook remain infra errors.
  check_ooxml(p,'xl/workbook.xml')
  import openpyxl
  f=openpyxl.load_workbook(p,data_only=False);v=openpyxl.load_workbook(p,data_only=True)
  sheets={}
  for s in f:
   if s.max_row*s.max_column>20000:raise ValueError('Workbook exceeds review cell budget')
   rows=[]
   for row in s:
    cells=[]
    for c in row:
     if c.value is not None:
      value=c.value.isoformat() if hasattr(c.value,'isoformat') else c.value
      cache=v[s.title][c.coordinate].value
      cache=cache.isoformat() if hasattr(cache,'isoformat') else cache
      cells.append({'cell':c.coordinate,'value':value,'cached':cache})
    if cells:rows.append(cells)
   sheets[s.title]={'state':s.sheet_state,'rows':rows}
  return {'type':'xlsx','sheets':sheets}
 if p.suffix.lower()=='.pdf':
  from pypdf import PdfReader
  return {'type':'pdf','pages':[{'physical_page':i+1,'text':page.extract_text()} for i,page in enumerate(PdfReader(p).pages)]}
 if p.suffix.lower()=='.csv':
  return {'type':'csv','rows':list(csv.DictReader(p.open(encoding='utf-8-sig')))}
 if p.suffix.lower()=='.html':
  # Original also remains available to the judge; parsed companion preserves numbering.
  from html.parser import HTMLParser
  class Parser(HTMLParser):
   def __init__(self):super().__init__();self.parts=[];self.skip=0
   def handle_starttag(self,tag,attrs):
    if tag in {'script','style'}:self.skip+=1
   def handle_endtag(self,tag):
    if tag in {'script','style'}:self.skip=max(0,self.skip-1)
   def handle_data(self,data):
    if not self.skip and data.strip():self.parts.append(data.strip())
  x=Parser();x.feed(p.read_text(errors='replace'));return {'type':'html','text':'\n'.join(x.parts)}
 return {'type':'text','text':p.read_text(encoding='utf-8-sig')}

def trusted_inputs(config):
 manifest=config.get('trusted_input_sha256')
 if not isinstance(manifest,dict) or not manifest:raise ValueError('Trusted input snapshot manifest missing')
 if not INP.is_dir():raise FileNotFoundError('Trusted input directory missing: '+str(INP))
 actual={p.name:p for p in INP.iterdir()}
 if set(actual)!=set(manifest):raise ValueError('Trusted input snapshot filenames differ: missing='+str(sorted(set(manifest)-set(actual)))+' unexpected='+str(sorted(set(actual)-set(manifest))))
 inputs={};hashes={}
 for name,expected_hash in sorted(manifest.items()):
  if Path(name).name!=name or not isinstance(expected_hash,str) or len(expected_hash)!=64 or any(c not in '0123456789abcdef' for c in expected_hash):raise ValueError('Invalid trusted input snapshot entry: '+str(name))
  p=actual[name]
  if not p.is_file():raise ValueError('Trusted input is not a regular file: '+name)
  hashes[name]=hashlib.sha256(p.read_bytes()).hexdigest()
  if hashes[name]!=expected_hash:raise ValueError('Trusted input snapshot SHA256 mismatch: '+name)
  if p.suffix.lower()=='.json':json.loads(p.read_text(encoding='utf-8-sig'))
  if p.suffix.lower() in {'.md','.txt','.json','.csv','.xlsx','.docx','.pdf','.html'}:inputs[name]=extract(p)
  else:raise ValueError('Unsupported trusted input format: '+name)
 dump('trusted-input-integrity.json',{'status':'passed','input_sha256':hashes,'scope':'Visible input snapshot integrity, not candidate answer matching'})
 return inputs

try:
 config=json.loads((ROOT/'evaluation-config.json').read_text());rubric=json.loads((ROOT/'rubric.json').read_text())
 inputs=trusted_inputs(config)
 expected=config['deliverables']; present={p.name:p for p in OUT.iterdir() if p.is_file()} if OUT.is_dir() else {}
 if not any(name in present for name in expected):
  assertions=[{'id':c['id'],'status':'failed','score':0,'max_points':c['points'],'reason':'No required deliverable submitted'} for c in rubric['criteria']]
  dump('report.json',{'valid':True,'mode':'empty-output','assertions':assertions,'reward':0});dump('reward.json',{'reward':0,'objective':0,'professional':0});sys.exit(0)
 outputs={};hashes={};extraction_errors=[];candidate_defects=[];readable_workbooks={}
 for name in expected:
  if name not in present:extraction_errors.append('Missing deliverable: '+name);continue
  p=present[name]
  if p.stat().st_size>15*1024*1024:raise ValueError('Output file exceeds 15MB review budget')
  try:
   hashes[name]=hashlib.sha256(p.read_bytes()).hexdigest()
   outputs[name]=extract(p)
   if p.suffix.lower()=='.xlsx':readable_workbooks[name]=p
  except ImportError as e:raise RuntimeError('Candidate extraction dependency unavailable: '+name+': '+str(e)) from e
  except Exception as e:
   error=name+': '+type(e).__name__+': '+str(e)
   extraction_errors.append(error);candidate_defects.append({'file':name,'error_type':type(e).__name__,'reason':str(e)})
 evaluated=OUT
 recomputation=[]
 if outputs:
  for p in present.values():
   if p.name in expected or p.suffix.lower()!='.xlsx':continue
   try:extract(p);readable_workbooks[p.name]=p
   except ImportError as e:raise RuntimeError('Candidate extraction dependency unavailable: '+p.name+': '+str(e)) from e
   except Exception as e:
    extraction_errors.append(p.name+': '+type(e).__name__+': '+str(e));candidate_defects.append({'file':p.name,'error_type':type(e).__name__,'reason':str(e)})
 if readable_workbooks:
  evaluated=LOG/'recalculated-output';evaluated.mkdir(exist_ok=True)
  for p in present.values():
   if any(d['file']==p.name for d in candidate_defects) and p.name not in hashes:continue
   if p.name not in readable_workbooks:shutil.copy2(p,evaluated/p.name)
   else:
    (evaluated/p.name).unlink(missing_ok=True)
    profile=LOG/('lo-profile-'+hashlib.sha256(p.name.encode()).hexdigest()[:10])
    command=['libreoffice','-env:UserInstallation='+profile.as_uri(),'--headless','--convert-to','xlsx:Calc MS Excel 2007 XML','--outdir',str(evaluated),str(p)]
    r=subprocess.run(command,capture_output=True,text=True,timeout=90)
    recomputation.append({'file':p.name,'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
    if r.returncode or not (evaluated/p.name).exists():raise RuntimeError('Native spreadsheet recalculation failed: '+p.name)
  dump('spreadsheet-recalculation.json',{'engine':'LibreOffice Calc','results':recomputation,'original_outputs_unchanged':True})
 proc=subprocess.run([sys.executable,str(ROOT/'objective.py'),str(evaluated)],capture_output=True,text=True,timeout=90)
 try:objective=json.loads(proc.stdout)
 except Exception:objective={'status':'error','stdout':proc.stdout[-5000:],'stderr':proc.stderr[-5000:]}
 if objective.get('status') not in {'passed','failed'}:raise ValueError('Objective checks did not execute successfully')
 for defect in candidate_defects:
  objective.setdefault('checks',[]).append({'id':'candidate-readable-'+defect['file'],'passed':False,'expected':'readable candidate deliverable','actual':defect,'reason':'Candidate file format/readability defect'})
  objective.setdefault('errors',[]).append(defect['file']+': '+defect['reason']);objective['status']='failed'
 dump('objective.json',objective)
 if not outputs:
  assertions=[{'id':c['id'],'status':'failed','score':0,'max_points':c['points'],'reason':'No readable required deliverable submitted','evidence':extraction_errors} for c in rubric['criteria']]
  dump('report.json',{'valid':True,'mode':'unreadable-output','assertions':assertions,'reward':0,'objective':objective,'output_sha256':hashes,'extraction_errors':extraction_errors,'candidate_defects':candidate_defects});dump('reward.json',{'reward':0,'objective':0,'professional':0});sys.exit(0)
 req={'schema_version':1,'task_id':config['task_id'],'instruction':(ROOT/'instruction.md').read_text(),'rubric':rubric,'evidence_context':(ROOT/'evidence-context.md').read_text() if (ROOT/'evidence-context.md').exists() else '', 'inputs':inputs,'outputs':outputs,'output_sha256':hashes,'objective':objective,'objective_returncode':proc.returncode,'extraction_errors':extraction_errors,'judge_rules':config['judge_rules'],'spreadsheet_recalculation':recomputation,'recalculated_workbooks':{name:extract(evaluated/name) for name in readable_workbooks}}
 if candidate_defects:req['candidate_defects']=candidate_defects
 source_images=[{'name':p.name,'media_type':'image/png','data':base64.b64encode(p.read_bytes()).decode()} for p in sorted((ROOT/'source-figures').glob('*.png'))]
 if source_images:req['source_images']=source_images
 canonical=json.dumps(req,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode();req['request_sha256']=hashlib.sha256(canonical).hexdigest()
 dump('judge-request.json',req)
 response_path=LOG/'judge-response.json'
 print('LEGAL_JUDGE_REQUEST_READY '+req['request_sha256'],flush=True)
 deadline=time.monotonic()+float(os.getenv('LEGAL_JUDGE_WAIT_SEC','900'))
 while not response_path.exists():
  if time.monotonic()>deadline:raise RuntimeError('Independent professional judge response missing; evaluation incomplete')
  time.sleep(0.5)
 response=json.loads(response_path.read_text())
 if response.get('request_sha256')!=req['request_sha256']:raise ValueError('Judge response belongs to a different output/request')
 if response.get('judge_kind') not in {'independent-model-rubric','independent-reviewer-rubric'}:raise ValueError('Unsupported professional judge evidence')
 scored={c['id']:c for c in response['criteria']};assertions=[];points=0
 if len(scored)!=len(response['criteria']):raise ValueError('Duplicate scored criterion')
 if set(scored)!={c['id'] for c in rubric['criteria']}:raise ValueError('Incomplete professional rubric response')
 for c in rubric['criteria']:
  s=scored[c['id']];score=s['score']
  if not isinstance(score,(int,float)) or isinstance(score,bool) or not 0<=score<=c['points']:raise ValueError('Invalid criterion score')
  if not s.get('reason') or not isinstance(s.get('evidence'),list):raise ValueError('Scored criterion needs reason and evidence')
  if score>0 and not s['evidence']:raise ValueError('Positive credit requires concrete candidate/input evidence')
  points+=score;assertions.append({'id':c['id'],'status':'passed' if score==c['points'] else 'failed','score':score,'max_points':c['points'],'reason':s['reason'],'evidence':s['evidence']})
 reward=points/sum(c['points'] for c in rubric['criteria'])
 if objective.get('status')=='error':raise ValueError('Objective checks did not execute successfully')
 report={'valid':True,'mode':response['judge_kind'],'request_sha256':req['request_sha256'],'output_sha256':hashes,'judge_identity':response.get('judge_identity'),'assertions':assertions,'points':points,'reward':reward,'objective':objective,'professional_evaluation':response,'executed_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 dump('report.json',report);dump('reward.json',{'reward':reward,'objective':int(objective.get('status')=='passed'),'professional':reward})
 print(json.dumps({'reward':reward,'points':points,'judge_kind':response['judge_kind']}))
except Exception as e:
 (LOG/'reward.json').unlink(missing_ok=True)
 dump('report.json',{'valid':False,'error_type':type(e).__name__,'error':str(e),'scope':'verifier infrastructure/extraction/judge failure, not task failure'})
 # Deliberately no reward: Harbor must report an invalid verifier instead of fabricating zero.
 sys.exit(2)
