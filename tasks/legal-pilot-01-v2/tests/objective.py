#!/usr/bin/env python3
"""Objective OOXML integrity/visible-arithmetic checks, not legal grading."""
import sys,json,zipfile,re,posixpath,datetime
from pathlib import Path
from xml.etree import ElementTree as ET
NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
checks=[];errors=[];facts={};deferred=[]
def check(i,ok,expected,actual,reason=''):
    checks.append(dict(id=i,passed=bool(ok),expected=expected,actual=actual,reason=reason))
def xlsx(path):
    with zipfile.ZipFile(path) as z:
        if z.testzip():raise ValueError('Invalid ZIP member')
        shared=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            shared=[''.join(e.itertext()) for e in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',NS)]
        rel={e.attrib['Id']:e.attrib['Target'] for e in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        sheets={}
        for sh in ET.fromstring(z.read('xl/workbook.xml')).findall('s:sheets/s:sheet',NS):
            target=rel[sh.attrib['{'+NS['r']+'}id']]
            name=target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
            data={}
            for c in ET.fromstring(z.read(name)).findall('.//s:sheetData/s:row/s:c',NS):
                v=c.find('s:v',NS);f=c.find('s:f',NS);t=c.get('t');value=None
                if t=='inlineStr':value=''.join(c.find('s:is',NS).itertext())
                elif v is not None and v.text is not None:
                    if t=='s':value=shared[int(v.text)]
                    elif t in ['str','e']:value=v.text
                    else:
                        try:value=float(v.text)
                        except ValueError:value=v.text
                data[c.get('r')]={'value':value,'formula':None if f is None else f.text,'type':t}
            sheets[sh.get('name')]=data
        return sheets
def norm(v):return re.sub(r'\s+','',str(v or ''))
def rownum(a):return int(re.search(r'\d+',a).group())
def col(a):return re.match(r'[A-Z]+',a).group()
def locate(data,label):
    return next((a for a,c in data.items() if norm(c['value'])==norm(label)),None)
def value_check(i,c,expect,tolerance=.01):
    value=c['value'] if c else None
    if value is None and c and c['formula']:
        deferred.append(i);check(i,True,expect,None,'Formula cache absent; recalculation and numeric assessment required by professional judge.');return
    check(i,isinstance(value,(int,float)) and abs(value-expect)<=tolerance,expect,value)
out=Path(sys.argv[1] if len(sys.argv)>1 else '/workspace/output')
try:
    doc=out/'修订合同.docx';book=out/'谈判台账.xlsx'
    check('files',doc.is_file() and book.is_file(),['修订合同.docx','谈判台账.xlsx'],sorted(p.name for p in out.iterdir()) if out.exists() else [])
    with zipfile.ZipFile(doc) as z:
        check('docx_integrity',z.testzip() is None and 'word/document.xml' in z.namelist(),'valid DOCX',z.testzip())
        text=''.join(ET.fromstring(z.read('word/document.xml')).itertext());facts['document_text_length']=len(text)
    sheets=xlsx(book);check('sheets',all(s in sheets for s in ['谈判事项','付款校核']),['谈判事项','付款校核'],list(sheets))
    data=sheets['付款校核'];headers=['比例合计','第一笔金额','第二笔金额','第三笔金额','金额合计','相对总价差额']
    expected={'原主文':[1.1,144000,240000,144000,528000,48000],'原附件B':[1,120000,240000,120000,480000,0],'修订建议':[1,96000,240000,144000,480000,0]}
    mapped=all(locate(data,h) for h in headers) and all(locate(data,label) for label in expected)
    if mapped:
        for label,nums in expected.items():
            r=rownum(locate(data,label))
            for h,n in zip(headers,nums):
                a=col(locate(data,h))+str(r);cell=data.get(a)
                value_check(label+'_'+h,cell,n,1e-8 if h=='比例合计' else .01)
                check(label+'_'+h+'_formula',bool(cell and cell['formula']),'editable calculation formula',cell['formula'] if cell else None)
        partial=['应结算','已付款','净应付','需返还']
        if all(locate(data,h) for h in partial):
            for h,n in zip(partial,[288000,96000,192000,0]):
                a=locate(data,h);cell=data.get(col(a)+str(rownum(a)+1));value_check('partial_'+h,cell,n)
                if h!='已付款':check('partial_'+h+'_formula',bool(cell and cell['formula']),'editable calculation formula',cell['formula'] if cell else None)
        else:deferred.append('partial_layout');facts['partial_layout']='Professional judge must locate equivalent partial settlement layout.'
    else:deferred.append('equivalent_layout');facts['numeric_layout']='Alternate labels/layout require professional judge numeric assessment; no template text matching.'
    f=[c for c in data.values() if c['formula']];check('editable_formulas',bool(f),'calculated amounts use formulas',len(f))
    ef=[c['value'] for s in sheets.values() for c in s.values() if c['type']=='e'];check('formula_errors',not ef,[],ef)
    facts['deferred_numeric_checks']=deferred
except Exception as e:errors.append(str(e));check('parse',False,'valid readable output',str(e))
result={'status':'passed' if not errors and all(c['passed'] for c in checks) else 'failed','checks':checks,'errors':errors,'scope':'objective only','facts':facts}
print(json.dumps(result,ensure_ascii=False));sys.exit(0 if result['status']=='passed' else 1)
