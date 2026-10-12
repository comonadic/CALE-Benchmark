#!/usr/bin/env python3
"""Read-only objective evidence. Professional conclusions are scored by the judge.

No legal-text matching. Unrecognised layouts or absent formula caches are deferred
to the judge instead of being treated as wrong. No matching against a reference file.
"""
from pathlib import Path
from collections import defaultdict
from datetime import date
from decimal import Decimal
import sys, json, csv, re, zipfile, math, xml.etree.ElementTree as ET
NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
CHECKS=[];ERRORS=[];DEFERRED=[]
def add(i,passed,expected=None,actual=None,reason=''):
    CHECKS.append(dict(id=i,passed=bool(passed),expected=expected,actual=actual,reason=reason))
    if not passed: ERRORS.append(i+': '+reason)
def num(i,actual,expected,tol):
    if actual is None:
        DEFERRED.append(dict(id=i,reason='saved formula cache unavailable; judge must inspect formula or recalculate'));return
    ok=isinstance(actual,(int,float)) and not isinstance(actual,bool) and math.isfinite(actual) and abs(actual-float(expected))<=tol
    add(i,ok,float(expected),actual,'numeric comparison within tolerance '+str(tol))
def read_xlsx(p):
    result=[]
    with zipfile.ZipFile(p) as z:
        bad=z.testzip()
        if bad: raise ValueError('invalid ZIP member '+bad)
        shared=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            shared=[''.join(t.text or '' for t in s.findall('.//s:t',NS)) for s in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',NS)]
        for sn in z.namelist():
            if not re.fullmatch(r'xl/worksheets/sheet\d+\.xml',sn):continue
            rows=[]
            for r in ET.fromstring(z.read(sn)).findall('.//s:sheetData/s:row',NS):
                row={}
                for c in r.findall('s:c',NS):
                    col=re.match('[A-Z]+',c.attrib['r']).group();typ=c.attrib.get('t','n');v=c.find('s:v',NS);val=v.text if v is not None else None
                    if typ=='s':val=shared[int(val)] if val is not None else None
                    elif typ=='inlineStr':val=''.join(t.text or '' for t in c.findall('.//s:t',NS))
                    elif typ=='e':add('formula-error-'+c.attrib['r'],False,'no spreadsheet error',val,sn)
                    elif typ not in ('str','b') and val is not None:
                        try:val=float(val)
                        except ValueError:pass
                    row[col]={'value':val,'formula':c.find('s:f',NS).text if c.find('s:f',NS) is not None else None}
                rows.append((int(r.attrib['r']),row))
            result.append((sn,rows))
    return result
def records(sheets,aliases,keyfields,valid):
    found={}
    for sn,rows in sheets:
        for ix,(rn,row) in enumerate(rows):
            cols={k:next((c for c,v in row.items() if str(v['value']).strip() in names),None) for k,names in aliases.items()}
            if not all(cols.get(k) for k in keyfields):continue
            if not any(cols.get(k) for k in aliases if k not in keyfields):continue
            for rnum,r in rows[ix+1:]:
                key=tuple(str(r.get(cols[k],{}).get('value','')).strip() for k in keyfields)
                key=valid(key)
                if key is None:continue
                rec={k:r.get(c,{'value':None,'formula':None}) for k,c in cols.items() if c}
                if key in found:
                    DEFERRED.append({'id':'duplicate-record','key':list(key),'reason':'multiple matching rows; judge must identify authoritative view'})
                found[key]={'sheet':sn,'row':rnum,'fields':rec}
    return found
def pick(row,field):return row['fields'].get(field,{}).get('value')
def audit_price(sheets,inp):
    groups=defaultdict(lambda:[0,0.,0.])
    for r in csv.DictReader((inp/'price-ledger.csv').open(encoding='utf-8')):
        if date(2024,10,9)<=date.fromisoformat(r['screen_date'])<date(2026,10,9):
            g=groups[r['city'],r['historical_operator']];g[0]+=1;g[1]+=float(r['units']);g[2]+=float(r['net_revenue_cny'])
    expected={}
    for r in csv.DictReader((inp/'price-plan.csv').open(encoding='utf-8')):
        plan=float(r['net_revenue_cny'])/float(r['units'])
        for op in ('分众','新潮'):
            n,u,a=groups[r['city'],op];b=a/u if n else None
            expected[r['city'],op]=dict(baseline=b,plan=plan,diff=plan-b if b is not None else None,pct=plan/b-1 if b is not None else None)
    aliases={'city':{'城市','city'},'op':{'历史主体','历史经营者','原经营者','historical_operator'},'baseline':{'历史代理价','历史加权单价','历史筛查单价','历史代理单价','historical_price_proxy'},'plan':{'计划代理价','计划年度单价','计划单价代理','plan_price_proxy'},'diff':{'差额（元/周）','差额(元/周)','单价差额','绝对差','price_delta'},'pct':{'比例差','百分比差','价格比例差','pct_delta'}}
    def valid(key):
        city,op=key
        if op.startswith('分众'):op='分众'
        elif op.startswith('新潮'):op='新潮'
        return (city,op) if (city,op) in expected else None
    found=records(sheets,aliases,['city','op'],valid)
    for key,values in expected.items():
        if key not in found:DEFERRED.append({'id':'price-layout','key':list(key),'reason':'mapping unavailable; judge must evaluate alternative table layout'});continue
        for field,target in values.items():
            if field not in found[key]['fields']:DEFERRED.append({'id':'price-field','key':list(key),'field':field,'reason':'column mapping unavailable'});continue
            actual=pick(found[key],field)
            if target is None:
                add('missing-history-'+field,not isinstance(actual,(int,float)) and bool(actual),'explicit missing indication',actual,'missing historical series must not be numeric zero')
            else:num('|'.join(key)+'-'+field,actual,target,0.0001 if field=='pct' else .01)
    return {'expected_prices':[dict(city=k[0],operator=k[1],**v) for k,v in expected.items()],'mapped_records':list(found.values()),'deferred':DEFERRED}
def audit_amount(sheets):
    values=[('R01',2020,'63973167.75','142.30'),('R02',2020,'63973167.75','471.03'),('R03',2021,'43712098.40','16.29'),('R04',2021,'4529090.07','5.07'),('R05',2022,'151418026.84','49.44'),('R06',2022,'11992778.71','13.49'),('R07',2023,'164224867.76','40.64'),('R08',2023,'17837345.39','27.61')]
    aliases={'id':{'比例ID','比例编号','ratio_id'},'year':{'年度','year'},'a':{'分子金额元','分子金额','numerator'},'p':{'公布百分数','公布比例百分数','percentage_points'},'point':{'点估计元','点估计','point_estimate'},'lower':{'下界元','下界','lower_bound'},'upper':{'上界元','上界','upper_bound'}}
    found=records(sheets,aliases,['id'],lambda k:k if k[0] in {v[0] for v in values} else None)
    for rid,year,a0,p0 in values:
        if (rid,) not in found:DEFERRED.append({'id':rid,'reason':'ratio row mapping unavailable; judge must inspect alternative table layout'});continue
        r=found[rid,];a=Decimal(a0);p=Decimal(p0)
        expected={'year':year,'a':a,'p':p,'point':a*100/p,'lower':a*100/(p+Decimal('.005')),'upper':a*100/(p-Decimal('.005'))}
        for field,t in expected.items():
            if field not in r['fields']:DEFERRED.append({'id':rid+'-'+field,'reason':'column mapping unavailable'});continue
            num(rid+'-'+field,pick(r,field),t,0 if field=='year' else .000001 if field=='p' else .005 if field=='a' else .1)
            if field in ('point','lower','upper'):
                add(rid+'-'+field+'-formula',bool(r['fields'][field].get('formula')),'auditable formula',r['fields'][field].get('formula'),'formula equivalence is evaluated by value and judge, not literal syntax')
    fines={'金铉玉':(3000000,3),'朱文龙':(3000000,3),'肖自然':(1500000,0),'曹放':(1500000,0),'包笠':(1500000,0),'任希宁':(1000000,0),'王能海':(500000,0),'王北':(500000,0)}
    people=records(sheets,{'name':{'姓名','name'},'fine':{'罚款元','罚款金额元','fine_yuan'},'ban':{'禁入年数','禁入年限','ban_years'}},['name'],lambda k:k if k[0] in fines else None)
    for name,(fine,ban) in fines.items():
        if (name,) not in people:DEFERRED.append({'id':name,'reason':'person row mapping unavailable'});continue
        for field,t in [('fine',fine),('ban',ban)]:
            if field not in people[name,]['fields']:DEFERRED.append({'id':name+'-'+field,'reason':'column mapping unavailable'});continue
            num(name+'-'+field,pick(people[name,],field),t,.005 if field=='fine' else 0)
    return {'mapped_ratios':list(found.values()),'mapped_people':list(people.values()),'deferred':DEFERRED}
def main():
    out=Path(sys.argv[1]) if len(sys.argv)>1 else Path('/workspace/output')
    task=Path(__file__).resolve().parents[1];inp=Path('/workspace/input-data') if Path('/workspace/input-data').is_dir() else task/'environment/input-data'
    isprice=(inp/'price-ledger.csv').exists();book=out/('compliance-control.xlsx' if isprice else '核查台账.xlsx');doc=out/('implementation-record.md' if isprice else '审改报告.docx');facts={}
    for f in (book,doc):add('file-'+f.name,f.is_file() and f.stat().st_size>0,'nonempty required file',f.exists(),'required deliverable')
    if book.exists():
        try:
            sheets=read_xlsx(book);add('xlsx-readable',True,'valid XLSX ZIP/XML',len(sheets),'read without modifying');facts=audit_price(sheets,inp) if isprice else audit_amount(sheets)
        except Exception as e:add('xlsx-readable',False,'valid XLSX ZIP/XML',str(e),'parse failure')
    if doc.exists():
        try:
            if isprice:txt=doc.read_text(encoding='utf-8');add('memo-utf8',bool(txt.strip()),'nonempty UTF-8',len(txt),'no semantic scoring')
            else:
                with zipfile.ZipFile(doc) as z:ET.fromstring(z.read('word/document.xml'));add('docx-readable',True,'valid DOCX ZIP/XML',True,'no semantic scoring')
        except Exception as e:add('document-readable',False,'valid requested document',str(e),'parse failure')
    result={'status':'failed' if ERRORS else 'passed','checks':CHECKS,'errors':ERRORS,'scope':'objective only','facts':facts,'deferred_to_professional_judge':DEFERRED,'limitations':'No legal judgment, no wording match, no native engine proof. Alternative layouts and missing caches require judge review.'}
    print(json.dumps(result,ensure_ascii=False,indent=2));return 1 if ERRORS else 0
if __name__=='__main__':raise SystemExit(main())
