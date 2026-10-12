#!/usr/bin/env python3
"""Only file, column, typed-date and audited-date checks; legal reasoning is judged separately."""
import sys,json,zipfile,re,posixpath,datetime
from pathlib import Path
from xml.etree import ElementTree as ET
NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
checks=[];errors=[];facts={}
def check(i,ok,expected,actual,reason=''):checks.append(dict(id=i,passed=bool(ok),expected=expected,actual=actual,reason=reason))
def norm(v):return re.sub(r'\s+','',str(v or ''))
def xlsx(path):
    with zipfile.ZipFile(path) as z:
        if z.testzip():raise ValueError('Invalid ZIP member')
        shared=[]
        if 'xl/sharedStrings.xml' in z.namelist():shared=[''.join(e.itertext()) for e in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',NS)]
        rel={e.attrib['Id']:e.attrib['Target'] for e in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        sheets={}
        for sh in ET.fromstring(z.read('xl/workbook.xml')).findall('s:sheets/s:sheet',NS):
            target=rel[sh.attrib['{'+NS['r']+'}id']];name=target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
            root=ET.fromstring(z.read(name));data={}
            for c in root.findall('.//s:sheetData/s:row/s:c',NS):
                v=c.find('s:v',NS);f=c.find('s:f',NS);t=c.get('t');value=None
                if t=='inlineStr':value=''.join(c.find('s:is',NS).itertext())
                elif v is not None and v.text is not None:
                    if t=='s':value=shared[int(v.text)]
                    elif t in ['str','e']:value=v.text
                    else:
                        try:value=float(v.text)
                        except ValueError:value=v.text
                data[c.get('r')]={'value':value,'formula':None if f is None else f.text,'type':t}
            sheets[sh.get('name')]=(data,root)
        native_tables=[]
        for name in z.namelist():
            if name.startswith('xl/tables/') and name.endswith('.xml'):
                table=ET.fromstring(z.read(name));af=table.find('s:autoFilter',NS)
                native_tables.append({'name':table.get('name'),'range':table.get('ref'),'autoFilter_range':af.get('ref') if af is not None else None})
        facts['native_tables']=native_tables
        return sheets
def locate(data,label):return next((a for a,c in data.items() if norm(c['value'])==norm(label)),None)
def col(a):return re.match(r'[A-Z]+',a).group()
def row(a):return int(re.search(r'\d+',a).group())
out=Path(sys.argv[1] if len(sys.argv)>1 else '/workspace/output')
original=Path(sys.argv[2]) if len(sys.argv)>2 else out
try:
    book=out/'action-calendar.xlsx';plan=out/'procedure-plan.md'
    check('files',book.is_file() and plan.is_file(),['action-calendar.xlsx','procedure-plan.md'],sorted(p.name for p in out.iterdir()) if out.exists() else [])
    s=plan.read_text(encoding='utf8');check('plan_readable',bool(s.strip()),'nonempty UTF-8 plan',len(s))
    sheets=xlsx(book);check('sheets',all(k in sheets for k in ['行动日历','输入事件']),['行动日历','输入事件'],list(sheets))
    layout_sheets=xlsx(original/'action-calendar.xlsx')
    data,root=sheets['行动日历'];headers=['ID','阶段状态','办理动作','触发日','期限量','期限单位','规则届满或边界日','内部目标日','责任人','下一步或待确认','依据']
    layout_root=layout_sheets['行动日历'][1]
    pane=layout_root.find('s:sheetViews/s:sheetView/s:pane',NS)
    facts['freeze_pane']=pane.attrib if pane is not None else None
    facts['workbook_evidence_roles']={'native_tables_and_freeze_pane':'original-delivery','numeric_dates_and_formula_errors':'evaluated-output','original_directory':str(original),'evaluated_directory':str(out)}
    mapped={h:locate(data,h) for h in headers};check('columns',all(mapped.values()),headers,[h for h,a in mapped.items() if a])
    expected={'A01':'2025-04-12','A02':'2025-04-12','A03':'2025-04-17','A04':'2025-04-17','A05':'2025-05-22','A06':'2025-04-10','A07':'2025-05-05','A08':'2025-05-10','A09':'2025-05-12','A10':'2025-05-07','A11':'2025-08-25','A12':'2025-07-25','A13':'2025-10-09','A14':'2025-10-09','A15':None,'A16':'2025-05-11','A17':'2025-10-31','A18':'2025-10-31'}
    ids={i:locate(data,i) for i in expected};check('ids',all(ids.values()),list(expected),[i for i,a in ids.items() if a])
    if all(mapped.values()) and all(ids.values()):
        gcol=col(mapped['规则届满或边界日']);dcol=col(mapped['触发日']);deferred=[]
        for i,date in expected.items():
            r=row(ids[i]);c=data.get(gcol+str(r),{});v=c.get('value');f=c.get('formula')
            if date is None:check(i+'_untriggered',v in [None,''],None,v,'Fee deadline is unknown until notification.')
            else:
                e=(datetime.date.fromisoformat(date)-datetime.date(1899,12,30)).days
                if v is None and f:deferred.append(i);check(i+'_date',True,date,None,'Formula cache absent; supported engine must recalculate before numeric grading.')
                else:check(i+'_date',isinstance(v,(int,float)) and abs(v-e)<1e-8,date,v)
                check(i+'_formula',bool(f),'recalculable formula',f)
        facts['deferred_date_checks']=deferred
    ef=[c['value'] for cells,r in sheets.values() for c in cells.values() if c['type']=='e'];check('formula_errors',not ef,[],ef)
    facts['calendar_rows']=len(ids);facts['professional_scope']='triggers, objections, authority, alternatives and legal citations require professional criterion scoring'
except Exception as e:errors.append(str(e));check('parse',False,'valid readable output',str(e))
result={'status':'passed' if not errors and all(c['passed'] for c in checks) else 'failed','checks':checks,'errors':errors,'scope':'objective only','facts':facts}
print(json.dumps(result,ensure_ascii=False));sys.exit(0 if result['status']=='passed' else 1)
