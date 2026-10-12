#!/usr/bin/env python3
"""90 typed audit points plus an explicitly external 10-point DOCX review.
No keyword/full-reference/hash whitelist is used to decide prose correctness.
Artifact hashes only bind a trusted independent review to these exact outputs.
"""
import argparse,csv,datetime,hashlib,json,math,re,unicodedata,xml.etree.ElementTree as ET,zipfile
from pathlib import Path
from decimal import Decimal,InvalidOperation
HERE=Path(__file__).resolve().parent
FIELDS={'correction_id','check_id','draft_id','action','topic','original_text','revised_text','checked_value','value_unit','evidence_role','rationale','source_refs','client_impact'}
W='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
PAGE_MAX={'F011':216,'F014':218,'F013':32}
ROLES={'clause':'clause','条款':'clause','直接条款':'clause','reported_stock':'reported_stock','报告日存量':'reported_stock','存量事实':'reported_stock','disclosed_event':'disclosed_event','披露事件':'disclosed_event','回溯发行事件':'disclosed_event','calculation':'calculation','计算':'calculation','换算':'calculation','inference':'inference','推断':'inference','有依据推断':'inference','not_confirmed':'not_confirmed','待核实':'not_confirmed','未确认':'not_confirmed'}
MONEY={'cny':Decimal(1),'元':Decimal(1),'人民币元':Decimal(1),'cny_10k':Decimal(10000),'万元':Decimal(10000),'cny_m':Decimal(1000000),'百万元':Decimal(1000000),'cny_100m':Decimal(100000000),'亿元':Decimal(100000000)}
UNIT_ALIASES={'%':'percent','百分比':'percent','倍':'multiple','年':'year','月':'month','个月':'month','次':'count','个工作日':'business_day','工作日':'business_day'}
ENUM_ALIASES={
 '其他一级资本':'AT1','其他一级资本工具':'AT1','二级资本':'T2','二级资本工具':'T2','核心一级资本':'CET1','扣除发行费用':'net_of_fees','净额':'net_of_fees','毛额':'gross',
 '发行人有权选择':'issuer_option','发行人选择':'issuer_option','自动':'automatic','未确认':'not_confirmed','待核实':'not_confirmed','资料不足以确认':'not_confirmed','已确认':'confirmed',
 '有依据推断':'supported_inference','高度吻合但待核标识码':'supported_inference','显名事实':'explicit_named_identity','无依据':'no_support','全部赎回':'all_only','全部而非部分':'all_only','部分或全部':'partial_or_all',
 '股东会':'shareholders_meeting','股东大会':'shareholders_meeting','经营层':'management','董事会':'board','可分配项目':'distributable_items','遵从适用法律':'follow_applicable_law','法律另有规定从其规定':'follow_applicable_law',
 '高于':'above','同顺位':'equal','相同':'equal','低于':'below','次于':'below','基准利率加固定利差每五年重置':'benchmark_plus_fixed_spread_reset5y','固定利率单利按年不计复利':'fixed_simple_annual_no_compounding',
 '簿记建档集中配售':'bookbuilding_and_allocation','自发行五年后每年付息日':'annual_distribution_after_year5','其他一级资本工具全部减记或转股后':'after_all_AT1_writedown_or_conversion',
 '同触发事件所有其他一级资本工具存续票面金额':'all_outstanding_AT1_same_trigger','同触发事件所有二级资本工具存续票面金额':'all_outstanding_T2_same_trigger',
 '满足监管本息偿付前提':'subject_to_regulatory_repayment_requirements','监管及相关部门认定通知公告日':'authority_determination_notice_and_announcement',
 '监管认定不减记无法生存或相关部门认定不公共支持无法生存的较早者':'earlier_of_regulator_writedown_OR_authority_public_support',
 '同等或更高质量资本替换且收入能力可持续或赎回后资本明显高于监管要求':'sustainable_same_or_better_capital_OR_materially_above_requirements',
 '次一工作日顺延不另计息':'next_business_day_no_extra_interest','决议次日起至恢复全额派息前':'day_after_resolution_until_resume_full_distribution'}
def norm(s):return unicodedata.normalize('NFKC',str(s)).strip()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
def page_range(s,maximum=218):
 m=re.fullmatch(r'(\d+)(?:\s*[-–—]\s*(\d+))?',s.strip())
 if not m:raise ValueError('page must be a number or a range')
 a,b=int(m[1]),int(m[2] or m[1])
 if a<1 or b<a or b>maximum:raise ValueError('invalid page range or nonexistent page')
 return set(range(a,b+1))
def citations(s):
 refs=[];errors=[]
 for raw in s.split(';'):
  try:
   fs=raw.strip().split('|')
   if len(fs)!=4 or not fs[1].startswith('physical:') or not fs[2].startswith('printed:') or not fs[3].startswith('clause:') or not fs[3][7:].strip():raise ValueError('citation field syntax')
   doc=fs[0]
   if doc not in PAGE_MAX:raise ValueError('unknown document')
   off=2 if doc=='F011' else 0
   ph=page_range(fs[1][9:],PAGE_MAX[doc]);pr=page_range(fs[2][8:],PAGE_MAX[doc]-off)
   if doc not in PAGE_MAX or max(ph)>PAGE_MAX[doc]:raise ValueError('unknown document or nonexistent page')
   if {p-off for p in ph}!=pr:raise ValueError('physical/printed page mapping mismatch')
   refs.append({'document_id':doc,'pages':sorted(ph),'raw':raw.strip()})
  except Exception as e:errors.append(str(e)+': '+raw)
 return refs,errors

def typed_value(row,f):
 raw=norm(row.get('checked_value',''));u=norm(row.get('value_unit','')).lower();typ=f['value_type'];expected=f['expected']
 if not raw:raise ValueError('missing checked_value')
 if typ=='number':
  try:n=Decimal(raw.replace(',','').replace(' ','').rstrip('%'))
  except InvalidOperation:raise ValueError('invalid number')
  if not n.is_finite():raise ValueError('number must be finite')
  eu=f['unit'].lower()
  if eu in MONEY:
   if u not in MONEY:raise ValueError('invalid CNY unit')
   v=n*MONEY[u]/MONEY[eu]
  elif eu=='percent':
   if u=='ratio':v=n*100
   elif UNIT_ALIASES.get(u,u)=='percent':v=n
   else:raise ValueError('rate must use percent or ratio')
  else:
   if UNIT_ALIASES.get(u,u)!=eu:raise ValueError('quantity unit mismatch')
   v=n
  tol=Decimal('0.0000001') if eu in ('percent','multiple') else Decimal('0.000001')
  return abs(v-Decimal(str(expected)))<=tol,str(v)
 if typ=='bool':
  if u not in ('bool','boolean'):raise ValueError('boolean unit mismatch')
  v={'true':True,'false':False,'yes':True,'no':False,'是':True,'否':False,'1':True,'0':False}.get(raw.lower())
  if v is None:raise ValueError('invalid boolean')
  return v==expected,v
 if typ=='date':
  if u!='date':raise ValueError('date unit mismatch')
  s=re.sub(r'[年/.]', '-',raw).replace('月','-').replace('日','')
  try:v=datetime.date.fromisoformat('-'.join([s.split('-')[0]]+['%02d'%int(x) for x in s.split('-')[1:]])).isoformat()
  except Exception:raise ValueError('invalid calendar date')
  return v==expected,v
 if typ=='monthday':
  if u!='monthday':raise ValueError('monthday unit mismatch')
  s=raw.replace('月','-').replace('日','').replace('/','-');parts=s.split('-')
  try:v='%02d-%02d'%(int(parts[0]),int(parts[1]));datetime.date.fromisoformat('2000-'+v)
  except Exception:raise ValueError('invalid month/day')
  return v==expected,v
 if typ=='enum':
  if u!='enum':raise ValueError('enum unit mismatch')
  v=ENUM_ALIASES.get(raw,raw)
  return v.lower()==str(expected).lower(),v
 if u!=f['unit'].lower():raise ValueError('text field unit mismatch')
 v=raw
 if f['check_id']=='A01':v={'大公国际':'大公国际资信评估有限公司','大公国际资信评估':'大公国际资信评估有限公司'}.get(v,v)
 if f['check_id']=='J01':v=raw.replace('年','-').replace('月末','').replace('月','');parts=v.split('-');v='%s-%02d'%(parts[0],int(parts[1]))
 return v==str(expected),v

def docx_precheck(path):
 errors=[];chars=0
 try:
  with zipfile.ZipFile(path) as z:
   root=ET.fromstring(z.read('word/document.xml'));chars=sum(len(n.text or '') for n in root.iter(W+'t'))
   if chars<300:errors.append('customer DOCX has less than300 editable text characters')
   if any(list(root.iter(W+x)) for x in ('ins','del','commentRangeStart','commentRangeEnd')):errors.append('unresolved revisions or comment anchors')
   if any(x.startswith('word/comments') for x in z.namelist()):errors.append('comments parts in clean DOCX')
 except Exception as e:errors.append('DOCX cannot be read: '+str(e))
 return {'passed':not errors,'errors':errors,'editable_text_characters':chars,'scope':'integrity and clean editable text only; full semantic correctness and rendered layout require independent review'}

def evaluate(output):
 output=Path(output);spec=json.loads((HERE/'facts.json').read_text());facts=spec['facts'];schema=[];rows=[]
 hashes={name:sha(output/name) for name in ('correction_log.csv','client_note_revised.docx')}
 try:
  with (output/'correction_log.csv').open(encoding='utf-8-sig',newline='') as inp:
   rd=csv.DictReader(inp);cols=rd.fieldnames or []
   if len(cols)!=len(set(cols)) or not FIELDS.issubset(cols):schema.append('missing or duplicate required columns')
   rows=list(rd)
 except Exception as e:schema.append('CSV cannot be read: '+str(e))
 keyed={};dupes=set();cid=set()
 for row in rows:
  k=row.get('check_id','').strip()
  if k in keyed:dupes.add(k)
  keyed[k]=row
  if row.get('correction_id') in cid:schema.append('duplicate correction_id')
  cid.add(row.get('correction_id'))
  if None in row:schema.append('row has excess cells')
 unknown=sorted(set(keyed)-{f['check_id'] for f in facts})
 if unknown:schema.append('unknown check_id: '+','.join(unknown))
 logs=[];critical=[]
 for f in facts:
  row=keyed.get(f['check_id']);errors=[];value_ok=role_ok=source_ok=False;normal=None;ref=[]
  if row is None:errors.append('missing check_id')
  else:
   if f['check_id'] in dupes:errors.append('duplicate check_id')
   if row.get('draft_id')!=f['draft_id']:errors.append('draft linkage wrong')
   if row.get('action') not in ('revise','retain','remove'):errors.append('action invalid')
   if f['draft_id']=='D13' and row.get('action')!='retain':errors.append('correct D13 fact must be retained')
   if any(not (row.get(k) or '').strip() for k in FIELDS):errors.append('required audit field empty')
   try:value_ok,normal=typed_value(row,f)
   except Exception as e:errors.append(str(e))
   role_ok=ROLES.get(norm(row.get('evidence_role','')))==f['evidence_role']
   ref,ce=citations(row.get('source_refs',''));errors.extend(ce)
   # Locator admissibility only. Page overlap is not proof of substantive support;
   # the independent reviewer reads the actual citation and candidate proposition.
   source_ok=not ce and all(any(r['document_id']==group['document_id'] for r in ref) for group in f['source_groups'])
   if f['critical'] and not value_ok and normal is not None:critical.append(f['check_id'])
  if errors or schema:value_ok=role_ok=source_ok=False
  pts=f['points']*((0.6+0.2*role_ok+0.2*source_ok) if value_ok else 0)
  logs.append({'check_id':f['check_id'],'criterion_id':f['criterion_id'],'draft_id':f['draft_id'],'points_available':f['points'],'points_awarded':pts,'value_correct':value_ok,'normalized_value':normal,'raw_value':row.get('checked_value') if row else None,'value_unit':row.get('value_unit') if row else None,'evidence_role_correct':role_ok,'source_locator_admissible':source_ok,'citations':ref,'errors':errors,'status':'passed' if value_ok and role_ok and source_ok and not errors else 'failed'})
 doc=docx_precheck(output/'client_note_revised.docx');auto=sum(x['points_awarded'] for x in logs)
 if not doc['passed']:auto=0
 cs=[]
 for k,p in spec['criterion_weights'].items():
  got=sum(x['points_awarded'] for x in logs if x['criterion_id']==k) if doc['passed'] else 0
  cs.append({'criterion_id':k,'points_available':p,'points_awarded':round(got,8),'status':'passed' if abs(got-p)<1e-6 else 'failed','method':'typed_audit_values_roles_and_admissible_locator_groups;independent_support_review_pending'})
 reviews=[{'criterion_id':k,'points_available':p,'points_awarded':0,'status':'pending','reason':'Await sealed independent review response.'} for k,p in [('DOCX01',5),('DOCX02',3),('DOCX03',2)]]
 review_critical=False;review_errors=[]
 review_pts=sum(x['points_awarded'] for x in reviews) if doc['passed'] else 0
 subtotal=auto+review_pts;total=min(subtotal,59) if critical or review_critical else subtotal
 pending=[x['criterion_id'] for x in reviews if x['status']=='pending']
 return {'version':2,'executed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'artifact_sha256':hashes,'automatic_points':round(auto,8),'independent_review_points':review_pts,'points_before_cap':round(subtotal,8),'total_points':round(total,8),'objective_fraction':round(total/100,8),'grading_complete':not pending,'pending_criteria':pending,'critical_error_check_ids':critical,'critical_error_by_reviewer':review_critical,'applied_cap':59 if critical or review_critical else None,'criteria':cs+reviews,'fact_results':logs,'schema_errors':schema,'docx_precheck':doc,'adjudication_errors':review_errors,'scope':'Automatic grading covers84 typed audit conclusions, evidence roles and direct source-clause page groups. It does not assess arbitrary free prose or layout. DOCX01-03 require trusted independent semantic/render review. Reference hashes are never used as an answer whitelist.'}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output-dir',default='/workspace/output');ap.add_argument('--log-dir',default='/logs/verifier');ap.add_argument('--objective-only',action='store_true');a=ap.parse_args();ld=Path(a.log_dir);ld.mkdir(parents=True,exist_ok=True)
 for name in ('reward.txt','reward.json','rewards.json'):(ld/name).unlink(missing_ok=True)
 try:r=evaluate(a.output_dir)
 except Exception as e:
  (ld/'report.json').write_text(json.dumps({'valid':False,'verifier_failed':True,'fatal_error':repr(e)})+'\n');raise
 r['reward_scope']='objective-only provisional fraction,not a finaltaskreward; shared rubric_bridge.py owns final reward'
 (ld/'criterion_report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:r.get(k) for k in ('automatic_points','independent_review_points','total_points','objective_fraction','grading_complete','pending_criteria','fatal_error')},ensure_ascii=False))
if __name__=='__main__':main()
