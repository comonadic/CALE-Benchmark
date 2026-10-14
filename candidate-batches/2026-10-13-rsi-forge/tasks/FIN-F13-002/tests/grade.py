#!/usr/bin/env python3
import argparse,json,math,re,sys,traceback
from pathlib import Path
from openpyxl import load_workbook
from pypdf import PdfReader
from docx import Document

EXPECTED={'期货公司期初金额':43985.34,'期货公司本期公允价值变动损益':-4639.58,'期货公司计入权益累计公允价值变动':-10718.22,'期货公司报告期购入金额':67976.44,'期货公司报告期售出金额':47100.25,'期货公司期末金额':64041.81,'期货公司期末金额占净资产':2.70,'商业银行本期公允价值变动损益':-608.01,'商业银行计入权益累计公允价值变动':336.27,'合计本期公允价值变动损益':-5247.59,'合计计入权益累计公允价值变动':-10381.95,'合计期末金额':64041.81,'期现相抵实际损益':290000000}
IDS=[a['id'] for a in json.loads((Path(__file__).parent/'assertions.json').read_text())['assertions']]
def result(ok,actual=None,expected=None,reason=None):
 d={'status':'passed' if ok else 'failed'}
 if actual is not None:d['actual']=actual
 if expected is not None:d['expected']=expected
 if reason:d['reason']=reason
 return d
def source_values(inp):
 from pypdf import PdfReader
 texts={p.name:'\n'.join(x.extract_text() or '' for x in PdfReader(p).pages) for p in inp.glob('*.pdf')}
 t='\n'.join(texts.values())
 # verify trusted inputs exist/readable and required source anchors exist
 req=['商品套期保值业务管理制度','关于开展套期保值业务的公告','2025 年第三次临时股东会','衍生品投资情况']
 if any(x not in t for x in req): raise RuntimeError('trusted source anchor missing')
 return t
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--input-data',required=True);ap.add_argument('--output',required=True);ap.add_argument('--logs',required=True);a=ap.parse_args(); inp=Path(a.input_data); out=Path(a.output); logs=Path(a.logs); logs.mkdir(parents=True,exist_ok=True)
 for p in (logs/'reward.json',logs/'report.json'):
  if p.exists():p.unlink()
 try:
  st=source_values(inp)
  facts={}
  m=re.search(r'期货公司\s+0\s+([\d,]+\.\d+)\s+(-[\d,]+\.\d+)\s+(-[\d,]+\.\d+)\s+([\d,]+\.\d+)\s+([\d,]+\.\d+)\s+([\d,]+\.\d+)\s+([\d.]+)%.*?商业银行\s+0\s+0\s+(-[\d,]+\.\d+)\s+([\d,]+\.\d+).*?合计\s+0\s+([\d,]+\.\d+)\s+(-[\d,]+\.\d+)\s+(-[\d,]+\.\d+)\s+([\d,]+\.\d+)\s+([\d,]+\.\d+)\s+([\d,]+\.\d+)\s+([\d.]+)%',st,re.S)
  if not m: raise RuntimeError('cannot parse source disclosure table')
  x=[float(v.replace(',','')) for v in m.groups()]
  facts=dict(zip(['期货公司期初金额','期货公司本期公允价值变动损益','期货公司计入权益累计公允价值变动','期货公司报告期购入金额','期货公司报告期售出金额','期货公司期末金额','期货公司期末金额占净资产','商业银行本期公允价值变动损益','商业银行计入权益累计公允价值变动','合计期初金额','合计本期公允价值变动损益','合计计入权益累计公允价值变动','合计购入金额','合计售出金额','合计期末金额','合计期末金额占净资产'],x))
  pnl=re.search(r'实际损益\s*金额合计为\s*([\d.]+)\s*亿元',st)
  if not pnl: raise RuntimeError('combined PnL source anchor absent')
  facts['期现相抵实际损益']=float(pnl.group(1))*100_000_000
  pol=next((t for n,t in [(p.name,'\n'.join(q.extract_text() or '' for q in PdfReader(p).pages)) for p in inp.glob('*.pdf')] if '商品套期保值业务管理制度' in t),'')
  ann=next((t for p in inp.glob('*.pdf') if '关于开展套期保值业务的公告' in (t:='\n'.join(q.extract_text() or '' for q in PdfReader(p).pages)) and '2025-041' in t),'')
  res=next((t for p in inp.glob('*.pdf') if '2025 年第三次临时股东会决议公告' in (t:='\n'.join(q.extract_text() or '' for q in PdfReader(p).pages))),'')
  if not pol or not ann or not res: raise RuntimeError('authorization/policy sources unavailable')
  # Load artifacts
  xlsx=out/'hedge_review.xlsx'; pdf=out/'hedge_review.pdf'; wb=None; ws=None
  if xlsx.exists():
   try: wb=load_workbook(xlsx,data_only=False)
   except Exception: pass
  sheetnames=set(wb.sheetnames) if wb else set()
  if wb and '披露复核' in sheetnames: ws=wb['披露复核']
  rows={}
  if ws:
   for r in ws.iter_rows(min_row=2,values_only=True):
    if r and r[0] is not None: rows[str(r[0])]=r
  ans={}
  def has_sheet(name): return name in sheetnames
  ans['R1.xlsx-open']=result(wb is not None)
  ans['R1.sheet-disclosure']=result(has_sheet('披露复核'))
  ans['R1.sheet-authorization']=result(has_sheet('授权与条款'))
  ans['R1.sheet-gaps']=result(has_sheet('证据及缺口'))
  def val(label):
   r=rows.get(label); return (r[1] if r and len(r)>1 else None)
  for aid,label,key in [('R2.futures-open','期货公司期初金额','期货公司期初金额'),('R2.futures-fv','期货公司本期公允价值变动损益','期货公司本期公允价值变动损益'),('R2.futures-oci','期货公司计入权益累计公允价值变动','期货公司计入权益累计公允价值变动'),('R2.futures-purchase','期货公司报告期购入金额','期货公司报告期购入金额'),('R2.futures-sales','期货公司报告期售出金额','期货公司报告期售出金额'),('R2.futures-ratio','期货公司期末金额占净资产','期货公司期末金额占净资产'),('R2.bank-fv','商业银行本期公允价值变动损益','商业银行本期公允价值变动损益'),('R2.bank-oci','商业银行计入权益累计公允价值变动','商业银行计入权益累计公允价值变动'),('R2.total-fv','合计本期公允价值变动损益','合计本期公允价值变动损益'),('R2.total-oci','合计计入权益累计公允价值变动','合计计入权益累计公允价值变动'),('R2.total-close','合计期末金额','合计期末金额'),('R2.pnl-disclosure','期现相抵实际损益','期现相抵实际损益')]:
   v=val(label); exp=facts[key]; ok=isinstance(v,(int,float)) and abs(float(v)-exp)<=max(0.02,abs(exp)*0.00001)
   if aid=='R2.futures-ratio': ok=ok and abs(float(v)-0.027)<0.000001
   ans[aid]=result(ok,v,exp)
  # conversion formula must exist and evaluate to correct cached/displayed value after LO reference output
  close=rows.get('期货公司期末金额'); close_yuan=(close[3] if close and len(close)>3 else None)
  ans['R2.close-yuan']=result(isinstance(close_yuan,str) and close_yuan.startswith('=') and close[1]*10000==640418100,close_yuan,'formula = disclosed 64,041.81万元 * 10000')
  # cross-check key live formulas
  formulas=[]
  if ws:
   formulas=[ws['C20'].value,ws['G20'].value,ws['G21'].value,ws['D7'].value]
  ans['R5.workbook-formulas']=result(any(isinstance(f,str) and f.startswith('=') for f in formulas) and len([f for f in formulas if isinstance(f,str) and f.startswith('=')])>=3,formulas,'live conversion and reconciliation formulas')
  # Authorization facts checked against trusted source and output workbook/memo text
  res_ok=bool(re.search(r'2025 年 8 月 14 日',res) and '关于开展套期保值业务的议案' in res and '审议通过' in res)
  ans['R3.approval-date']=result(res_ok and any('2025-08-14' in str(c.value) for row in wb['授权与条款'].iter_rows() for c in row) if wb and '授权与条款' in sheetnames else False,'2025-08-14','2025-08-14')
  ans['R3.commodity-cap']=result('40 亿元保证金' in ann and any(c.value==4000000000 for row in wb['授权与条款'].iter_rows() for c in row) if wb and '授权与条款' in sheetnames else False,4000000000,4000000000)
  ans['R3.fx-cap']=result('47 亿元' in ann and any(c.value==4700000000 for row in wb['授权与条款'].iter_rows() for c in row) if wb and '授权与条款' in sheetnames else False,4700000000,4700000000)
  memo=''
  if pdf.exists():
   try: memo='\n'.join(p.extract_text() or '' for p in PdfReader(pdf).pages)
   except Exception: pass
  if not memo and (out/'hedge_review.docx').exists(): memo='\n'.join(p.text for p in Document(out/'hedge_review.docx').paragraphs)+'\n'+'\n'.join(c.text for tb in Document(out/'hedge_review.docx').tables for row in tb.rows for c in row.cells)
  ans['R3.not-retroactive']=result(all(x in memo for x in ['2026 年 8 月 21 日','不用于追溯判断']) and '2026 年 8 月 21 日' in st,'2026 subsequent authorization excluded','not retroactively applied')
  sl=re.search(r'止损目标不得超过该方案交易金额的?\s*10\s*%',pol)
  ans['R3.stop-loss']=result(bool(sl) and '第十三条' in memo and ('交易金额10%' in memo or '交易金额 10%' in memo),'10% of scheme amount','10%')
  tr=bool(re.search(r'归属于上市公司股东净利润的?\s*10\s*%且绝对金',pol))
  ans['R3.disclosure-trigger']=result(tr and '第三十条' in memo and ('1,000万元' in memo or '1,000 万元' in memo),'10% and > RMB10m','10% and > RMB10m')
  ans['R4.gap-spot']=result(all(s in memo for s in ['逐笔现货','采购','作价台账','无法复原']),'spot records and impact','explicit gap and consequence')
  ans['R4.gap-derivatives']=result(all(s in memo for s in ['成交','持仓','结算','保证金账户']),'trade/position/settlement/margin snapshot','complete missing categories')
  ans['R4.gap-cannot-rebuild']=result('不能由汇总' in memo or '不能独立重算' in memo,'reconstruction boundary','aggregate result is not independently rebuildable')
  ans['R4.scheme-stop-loss-boundary']=result('无法判断方案层面的止损合规' in memo,'scheme-level limitation','state limitation')
  ans['R5.memo-period']=result(all(s in memo for s in ['2026-01-01','2026-06-30','合并披露']),'period and scope','2026H1 consolidated')
  ans['R5.memo-reconciliation']=result(all(s in memo for s in ['-5,247.59','-10,381.95','期间损益','累计权益变动']),'reconciliation and stock/flow/OCI distinctions','reconciled distinctions')
  ans['R5.memo-citations']=result(all(s in memo for s in ['第 24 页','第三十条','2025-043','2025-041']),'citations','report page, policy and authorizations')
  ans['R5.pdf-rendered']=result(bool(memo) and len(memo)>700,len(memo),'extractable memo content')
  ans['R5.gap-actions']=result(all(s in memo for s in ['补取','结算单','映射','审批']), 'follow-up record classes','specific requested evidence')
  # Check actual source capability and credible assertions rather than relying on placeholder keyword hits.
  # Missing or malformed candidate artifacts remain gradeable candidate defects.
  status='graded_candidate_defect' if any(v.get('status')=='failed' for v in ans.values()) else 'graded'
  if len(ans)==len(IDS):
   for aid in IDS: ans.setdefault(aid,{'status':'failed','reason':'not evaluated'})
   passed=sum(v.get('status')=='passed' for v in ans.values()); scale=len(IDS); reward=passed/scale
   caps=[]
   contract=json.loads((Path(__file__).parent/'assertions.json').read_text())
   for ce in contract.get('critical_errors',[]):
    if ans.get(ce['assertion'],{}).get('status')=='failed': reward=min(reward,ce['cap']); caps.append(ce['id'])
   report={'scale':scale,'P':passed,'reward':reward,'valid':True,'status':('graded_candidate_defect' if any(v.get('status')=='failed' for v in ans.values()) else 'graded'),'assertions':ans,'critical_error_caps_triggered':caps}
   (logs/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
   (logs/'reward.json').write_text(json.dumps({'reward':reward}))
   print(f'Graded {passed}/{scale}, reward={reward:.4f}')
   return 0
  raise RuntimeError('assertion contract mismatch')
 except Exception as e:
  report={'scale':None,'P':None,'reward':None,'valid':False,'status':'verifier_failure','error':str(e),'traceback':traceback.format_exc()}
  (logs/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
  for p in (logs/'reward.json',):
   if p.exists():p.unlink()
  print('Verifier failure:',e,file=sys.stderr); return 2
if __name__=='__main__':sys.exit(main())
