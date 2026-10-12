"""Evidence-backed partial automatic scoring, with artifact-bound human adjudication.

No reference coordinates or memo keyword matching. Workbook handoff tables are
discovered by public field names, and formulas are recalculated from the XLSX.
Unsupported interpreter syntax falls back to real LibreOffice, never cache-only.
"""
import argparse, ast, copy, hashlib, json, os, posixpath, re, shutil, subprocess, tempfile, zipfile
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import xml.etree.ElementTree as ET

NS={'x':'http://schemas.openxmlformats.org/spreadsheetml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
REF=re.compile(r"(?<![\w])(?:(?:'([^']+)'|([\w\u4e00-\u9fff ]+))!)?(\$?[A-Z]{1,3}\$?\d+)(?::(\$?[A-Z]{1,3}\$?\d+))?(?![\w(])")
ZERO=Decimal(0)
class FormulaError(Exception): pass
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def colnum(s):
    n=0
    for c in s:n=n*26+ord(c)-64
    return n
def colname(n):
    out=''
    while n:n,k=divmod(n-1,26);out=chr(k+65)+out
    return out
def cellparts(c):
    m=re.fullmatch(r'([A-Z]+)(\d+)',c.replace('$',''))
    if not m:raise FormulaError('Invalid cell '+c)
    return colnum(m[1]),int(m[2])
def flatten(x):
    if isinstance(x,list):
        for a in x:yield from flatten(a)
    else:yield x
def numeric(x):
    if isinstance(x,Decimal):return x
    if isinstance(x,bool):return Decimal(int(x))
    if x is None or x=='':return ZERO
    try:return Decimal(str(x))
    except Exception:raise FormulaError('Non-numeric calculation input '+str(x))
def vector(a,b,fn):
    if isinstance(a,list) or isinstance(b,list):
        a=a if isinstance(a,list) else [a]*len(b);b=b if isinstance(b,list) else [b]*len(a)
        if len(a)!=len(b):raise FormulaError('Array length mismatch')
        return [vector(x,y,fn) for x,y in zip(a,b)]
    return fn(numeric(a),numeric(b))

class Book:
    def __init__(self,path):
        self.path=Path(path);self.cells={};self.sheet_paths={};self.cache={};self.overrides={};self.names={}
        with zipfile.ZipFile(path) as z:
            if sum(i.file_size for i in z.infolist())>100_000_000:raise FormulaError('Workbook uncompressed size exceeds 100MB')
            strings=[]
            if 'xl/sharedStrings.xml' in z.namelist():
                for si in ET.fromstring(z.read('xl/sharedStrings.xml')):strings.append(''.join(t.text or '' for t in si.iter('{'+NS['x']+'}t')))
            w=ET.fromstring(z.read('xl/workbook.xml'));rels={r.attrib['Id']:r.attrib['Target'] for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
            dn=w.find('x:definedNames',NS)
            if dn is not None:
                for n in dn:self.names[n.attrib['name']]=n.text or ''
            for s in w.find('x:sheets',NS):
                sn=s.attrib['name'];target=rels[s.attrib['{'+NS['r']+'}id']]
                target=target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
                self.sheet_paths[sn]=target;shared={}
                for c in ET.fromstring(z.read(target)).findall('.//x:sheetData/x:row/x:c',NS):
                    f=c.find('x:f',NS);v=c.find('x:v',NS);t=c.attrib.get('t','n');value=v.text if v is not None else None
                    if t=='s':value=strings[int(value)] if value is not None else ''
                    elif t=='inlineStr':value=''.join(n.text or '' for n in c.iter('{'+NS['x']+'}t'))
                    elif t=='n' and value is not None:value=Decimal(value)
                    elif t=='b':value=value=='1'
                    formula=f.text if f is not None else None
                    if f is not None and f.attrib.get('t')=='shared':
                        si=f.attrib['si']
                        if formula:shared[si]=(c.attrib['r'],formula)
                        elif si in shared:
                            origin,formula=shared[si];oc,orr=cellparts(origin);nc,nr=cellparts(c.attrib['r'])
                            def shift(m):
                                prefix="'"+m[1]+"'!" if m[1] else m[2]+'!' if m[2] else ''
                                def one(a):
                                    col,row=cellparts(a);cm=re.match(r'(\$?)[A-Z]+(\$?)',a)
                                    return cm[1]+colname(col if cm[1] else col+nc-oc)+cm[2]+str(row if cm[2] else row+nr-orr)
                                return prefix+one(m[3])+(':'+one(m[4]) if m[4] else '')
                            formula=REF.sub(shift,formula)
                        else:raise FormulaError('Unresolved shared formula')
                    self.cells[(sn,c.attrib['r'])]={'formula':formula,'value':value,'type':t}
        if len(self.cells)>250_000:raise FormulaError('Workbook has too many populated cells')
    def raw(self,key):return self.cells.get(key,{}).get('value')
    def references(self,key):
        f=self.cells.get(key,{}).get('formula') or '';refs=[]
        for name,formula in self.names.items():
            if re.search(r'(?<![\w.])'+re.escape(name)+r'(?![\w.])',f):f=re.sub(r'(?<![\w.])'+re.escape(name)+r'(?![\w.])','('+formula+')',f)
        for m in REF.finditer(f):
            s=m[1] or m[2] or key[0];a=m[3].replace('$','');b=m[4]
            if b:
                c1,r1=cellparts(a);c2,r2=cellparts(b)
                if (c2-c1+1)*(r2-r1+1)>100000:raise FormulaError('Oversized formula range')
                refs.extend((s,colname(c)+str(r)) for r in range(r1,r2+1) for c in range(c1,c2+1))
            else:refs.append((s,a))
        return refs
    def leaves(self,key,stack=()):
        if key in stack:raise FormulaError('Circular calculation')
        if not self.cells.get(key,{}).get('formula'):return {key} if isinstance(self.raw(key),Decimal) else set()
        result=set()
        for r in self.references(key):result.update(self.leaves(r,stack+(key,)))
        return result
    def value(self,key,stack=()):
        if key in self.overrides:return self.overrides[key]
        if key in self.cache:return self.cache[key]
        if key in stack:raise FormulaError('Circular formula '+str(key))
        c=self.cells.get(key,{});f=c.get('formula')
        if not f:
            if c.get('type')=='e':raise FormulaError('Spreadsheet error '+str(c.get('value')))
            return c.get('value',ZERO)
        if len(f)>20000:raise FormulaError('Formula too long')
        f=f.lstrip('=');refs={}
        for name,formula in self.names.items():f=re.sub(r'(?<![\w.])'+re.escape(name)+r'(?![\w.])','('+formula+')',f)
        def sub(m):
            s=m[1] or m[2] or key[0];a=m[3].replace('$','');b=m[4]
            if b:
                c1,r1=cellparts(a);c2,r2=cellparts(b)
                val=[self.value((s,colname(cc)+str(rr)),stack+(key,)) for rr in range(r1,r2+1) for cc in range(c1,c2+1)]
            else:val=self.value((s,a),stack+(key,))
            token='REF_'+str(len(refs));refs[token]=val;return token
        f=REF.sub(sub,f).replace('_xlfn.','').replace('^','**').replace(';',',').replace('<>','!=')
        f=re.sub(r'(?<![<>=!])=(?!=)','==',f)
        f=re.sub(r'(\d+(?:\.\d+)?)%',r'(\1/100)',f)
        try:tree=ast.parse(f,mode='eval')
        except Exception as e:raise FormulaError('Unsupported formula syntax '+c['formula']) from e
        def ev(n):
            if isinstance(n,ast.Expression):return ev(n.body)
            if isinstance(n,ast.Constant):return Decimal(str(n.value)) if isinstance(n.value,(int,float)) else n.value
            if isinstance(n,ast.Name):
                if n.id in refs:return refs[n.id]
                if n.id.upper() in ['TRUE','FALSE']:return n.id.upper()=='TRUE'
            if isinstance(n,ast.UnaryOp):
                a=ev(n.operand)
                if isinstance(n.op,ast.USub):return vector(a,Decimal(-1),lambda x,y:x*y)
                if isinstance(n.op,ast.UAdd):return a
                if isinstance(n.op,ast.Not):return not a
            if isinstance(n,ast.BinOp):
                a,b=ev(n.left),ev(n.right)
                operations={ast.Add:lambda x,y:x+y,ast.Sub:lambda x,y:x-y,ast.Mult:lambda x,y:x*y,ast.Div:lambda x,y:x/y,ast.Pow:lambda x,y:x**y}
                if type(n.op) in operations:return vector(a,b,operations[type(n.op)])
            if isinstance(n,ast.Compare):
                a=ev(n.left);b=ev(n.comparators[0]);ops={ast.Eq:lambda:a==b,ast.NotEq:lambda:a!=b,ast.Lt:lambda:a<b,ast.LtE:lambda:a<=b,ast.Gt:lambda:a>b,ast.GtE:lambda:a>=b}
                return ops[type(n.ops[0])]()
            if isinstance(n,ast.Call) and isinstance(n.func,ast.Name):
                fn=n.func.id.upper()
                if fn=='IF':return ev(n.args[1] if ev(n.args[0]) else n.args[2])
                if fn=='IFERROR':
                    try:return ev(n.args[0])
                    except (FormulaError,ArithmeticError):return ev(n.args[1])
                args=[ev(a) for a in n.args];vals=[x for x in flatten(args) if isinstance(x,(Decimal,bool))]
                if fn=='SUM':return sum(vals,ZERO)
                if fn=='SUMPRODUCT':
                    arrays=[a if isinstance(a,list) else [a] for a in args]
                    if len({len(a) for a in arrays})!=1:raise FormulaError('SUMPRODUCT dimensions')
                    products=[]
                    for items in zip(*arrays):
                        p=Decimal(1)
                        for x in items:p*=numeric(x)
                        products.append(p)
                    return sum(products,ZERO)
                if fn=='PRODUCT':
                    p=Decimal(1)
                    for x in vals:p*=x
                    return p
                if fn=='ABS':return abs(numeric(args[0]))
                if fn=='MIN':return min(vals)
                if fn=='MAX':return max(vals)
                if fn=='AVERAGE':return sum(vals,ZERO)/len(vals)
                if fn=='ROUND':return numeric(args[0]).quantize(Decimal(10)**-int(args[1]),rounding=ROUND_HALF_UP)
                if fn=='INDEX':return args[0][int(args[1])-1]
                if fn=='MATCH':return Decimal(args[1].index(args[0])+1)
                if fn in ['AND','OR']:return all(args) if fn=='AND' else any(args)
            raise FormulaError('Unsupported formula '+c['formula'])
        try:value=ev(tree)
        except ArithmeticError as e:raise FormulaError(str(e)) from e
        self.cache[key]=value;return value
    def reset(self,overrides=None):self.cache={};self.overrides=overrides or {}
    def native(self):
        """Recalculate a disposable XLSX with actual LibreOffice for broad formulas."""
        binary=os.environ.get('SOFFICE') or shutil.which('soffice')
        if not binary:raise FormulaError('Unsupported interpreter syntax and LibreOffice is unavailable')
        with tempfile.TemporaryDirectory(prefix='finance-verifier-') as td:
            td=Path(td);src=td/'input';out=td/'output';src.mkdir();out.mkdir();dest=src/self.path.name
            parts={p:[] for p in self.sheet_paths.values()}
            for (s,c),v in self.overrides.items():parts[self.sheet_paths[s]].append((c,v))
            with zipfile.ZipFile(self.path) as zin,zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as zout:
                for member in zin.infolist():
                    body=zin.read(member.filename)
                    if member.filename in parts:
                        xml=ET.fromstring(body)
                        cells={c.attrib['r']:c for c in xml.findall('.//x:sheetData/x:row/x:c',NS)}
                        # Discard every formula cache before opening. Exported
                        # caches can otherwise mask an input-only ZIP mutation.
                        for c in cells.values():
                            if c.find('x:f',NS) is not None:
                                for cached in c.findall('x:v',NS):c.remove(cached)
                        for address,val in parts[member.filename]:
                            c=cells[address];c.attrib['t']='n'
                            for sub in list(c):c.remove(sub)
                            ET.SubElement(c,'{'+NS['x']+'}v').text=str(val)
                        body=ET.tostring(xml,encoding='utf-8',xml_declaration=True)
                    elif member.filename=='xl/workbook.xml':
                        xml=ET.fromstring(body);calc=xml.find('x:calcPr',NS)
                        if calc is None:calc=ET.SubElement(xml,'{'+NS['x']+'}calcPr')
                        calc.attrib.update(calcMode='auto',fullCalcOnLoad='1',forceFullCalc='1')
                        body=ET.tostring(xml,encoding='utf-8',xml_declaration=True)
                    zout.writestr(member,body)
            proc=subprocess.run([binary,'-env:UserInstallation=file://'+str(td/'profile'),'--headless','--convert-to','xlsx','--outdir',str(out),str(dest)],capture_output=True,text=True,timeout=90)
            result=out/self.path.name
            if proc.returncode or not result.exists():raise FormulaError('LibreOffice recalc failed: '+proc.stderr[:500])
            recalced=Book(result)
            for key,c in recalced.cells.items():self.cache[key]=c.get('value')
            if any(c.get('type')=='e' for c in recalced.cells.values()):raise FormulaError('LibreOffice produced formula errors')
        return 'LibreOffice native recalculation'

def calculate(f,codes,groups):
    def val(code,y):return f[code+'_'+str(y)]
    m={}
    for y,suffix in [(2024,'24'),(2025,'25')]:
        np=val('NP',y);cfo=sum((val(c,y) for c in codes),ZERO)
        m.update({'NP'+suffix:np,'CFO'+suffix:cfo,'RATIO'+suffix:cfo/np,'SPREAD'+suffix:cfo-np})
        m['CFO_CONTROL_'+str(y)]=cfo-val('CFO',y)
        m['NP_CONTROL_'+str(y)]=val('MAIN_NP',y)-np
        m['ATTRIBUTION_CONTROL_'+str(y)]=val('PARENT_NP',y)+val('MINORITY_NP',y)-val('MAIN_NP',y)
        m['DIRECT_CF_CONTROL_'+str(y)]=val('CF_IN',y)-val('CF_OUT',y)-val('CFO',y)
        m['INV_NET_CONTROL_'+str(y)]=val('INV_GROSS',y)-val('INV_ALLOW',y)-val('INV_NET',y)
        m['AR_NET_CONTROL_'+str(y)]=val('AR_GROSS',y)-val('AR_ALLOW',y)-val('AR_NET',y)
        m['CL_CONTROL_'+str(y)]=sum((val(c,y) for c in ['CL_CUSTOMER','CL_CARD','CL_OTHER']),ZERO)-val('CL_TOTAL',y)
    for c in codes:m[c+'_CONTRIB']=val(c,2025)-val(c,2024)
    m['CFO_DELTA']=m['CFO25']-m['CFO24'];m['NP_DELTA']=m['NP_CONTRIB'];m['RECEIVABLE_CONTRIB']=m['RECEIVABLE_CF_CONTRIB'];m['PAYABLE_CONTRIB']=m['PAYABLE_CF_CONTRIB']
    m['WC_DELTA']=sum((m[c+'_CONTRIB'] for c in codes if groups[c]=='营运资本调整'),ZERO)
    m['NONWC_DELTA']=sum((m[c+'_CONTRIB'] for c in codes if groups[c]=='非营运资本调整'),ZERO)
    m['CONTRIB_CONTROL']=sum((m[c+'_CONTRIB'] for c in codes),ZERO)-(val('CFO',2025)-val('CFO',2024))
    for c in ['INV_GROSS','INV_ALLOW','INV_NET','AR_GROSS','AR_ALLOW','AR_NET','AP','CL_CUSTOMER','CL_CARD','CL_OTHER','CL_TOTAL']:
        m[c.replace('CL_TOTAL','CL')+'_DELTA']=val(c,2025)-val(c,2024)
    m['INV_ALLOW_ROLL']=val('INV_ALLOW',2024)+val('INV_CHARGE',2025)-val('INV_RELEASE',2025)
    m['INV_ALLOW_CONTROL_2025']=m['INV_ALLOW_ROLL']-val('INV_ALLOW',2025)
    m['INV_NET_GAP']=val('INVENTORY_CF',2025)+m['INV_NET_DELTA']
    m['INV_GROSS_GAP']=val('INVENTORY_CF',2025)+m['INV_GROSS_DELTA']
    m['INV_CF_NET']=-m['INV_NET_DELTA']-val('INV_CHARGE',2025)
    m['INV_CF_GROSS']=-m['INV_GROSS_DELTA']-val('INV_RELEASE',2025)
    m['INV_NET_CF_CONTROL']=m['INV_CF_NET']-val('INVENTORY_CF',2025)
    m['INV_GROSS_CF_CONTROL']=m['INV_CF_GROSS']-val('INVENTORY_CF',2025)
    m['AR_RESIDUAL']=val('RECEIVABLE_CF',2025)+m['AR_NET_DELTA']
    m['AP_RESIDUAL']=val('PAYABLE_CF',2025)-m['AP_DELTA']
    m['AP_CAPITAL_EXAMPLES']=val('AP_PROPERTY',2025)+val('AP_ENGINEER',2025)
    return m

ALIASES={'指标ID':'id','指标id':'id','metric_id':'id','金额/结果':'value','金额／结果':'value','value':'value','元/单位':'scale','yuan_per_unit':'scale','来源页':'page','source_page':'page','范围':'scope','scope':'scope','期间':'period','period':'period','分组':'group','group':'group','绝对贡献排名':'rank','absolute_rank':'rank'}
def discover(b):
    tables=[];index={};duplicates=[]
    for s in b.sheet_paths:
        rows={}
        for (sn,c),v in b.cells.items():
            if sn==s:
                col,r=cellparts(c);rows.setdefault(r,{})[col]=v.get('value')
        for r,cols in sorted(rows.items()):
            headers={ALIASES[str(v).strip()]:col for col,v in cols.items() if str(v).strip() in ALIASES}
            if not {'id','value','scale','page','scope','period'}<=headers.keys():continue
            tables.append({'sheet':s,'header_row':r,'headers':headers})
            for rr,vals in sorted(rows.items()):
                if rr<=r:continue
                id=str(vals.get(headers['id'],'')).strip()
                if not id or id in ALIASES:continue
                if id in index:duplicates.append(id);continue
                entry={field:vals.get(col) for field,col in headers.items()}
                entry['key']=(s,colname(headers['value'])+str(rr));index[id]=entry
    return index,tables,duplicates

MANUAL={'M1':{'points':5,'object':'现金转换、贡献方向、组合及算术贡献与经营因果的边界'},'M2':{'points':5,'object':'存货准备算术关系、采购现金边界、转回与转销未拆分'},'M3':{'points':7,'object':'应收应付与合同负债范围、资本款性质、未对平残差及两项具体补证'},'M4':{'points':3,'object':'备忘录事实计算判断区分、真实页码、对应工作簿位置与可读性'}}

def evaluate(output,expected_path):
    output=Path(output);defs=json.loads(Path(expected_path).read_text());checks=[];criteria=[];engines=[]
    def add(id,group,ok,details):checks.append({'check_id':id,'criterion_id':group,'status':'passed' if ok else 'failed','details':details});return ok
    bookfile=output/'cashflow-review.xlsx';memofile=output/'investment-note.md'
    hashes={p.name:sha(p) for p in [bookfile,memofile] if p.is_file()}
    if not bookfile.is_file():
        return {'status':'failed','reward':0.0,'automatic_points':0,'semantic_points':0,'pending_semantic_points':20,'artifact_hashes':hashes,'criteria':[{'criterion_id':id,'points_awarded':0,'status':'failed','reason':'missing workbook'} for id in ['R1','R2','R3','R4','R5','R6']], 'checks':[{'check_id':'missing_workbook','status':'failed','details':'cashflow-review.xlsx is absent'}], 'semantic_criteria':[{ 'criterion_id':id,**v,'status':'not_applicable','points_awarded':0} for id,v in MANUAL.items()]}
    b=Book(bookfile);index,tables,duplicates=discover(b)
    add('handoff_index','R6',bool(tables) and not duplicates,{'tables':tables,'duplicate_ids':duplicates})
    metric_ok={};fact_value_ok={};fact_meta_ok={};fact_page_ok={};leaves=set()
    def getval(id):
        row=index[id];return numeric(b.value(row['key']))*numeric(row['scale'])
    def evaluate_values(ids):
        try:return {id:getval(id) for id in ids}
        except (FormulaError,ArithmeticError) as e:
            engines.append({'engine':'fallback','reason':str(e)});engines.append({'engine':b.native()});return {id:getval(id) for id in ids}
    present=[id for id in list(defs['facts'])+list(defs['metrics']) if id in index]
    values=evaluate_values(present)
    for id,rule in defs['facts'].items():
        row=index.get(id,{});actual=values.get(id);expected=Decimal(rule['value'])
        fact_value_ok[id]=add('source_value:'+id,'R1',actual is not None and abs(actual-expected)<=Decimal('.02'),{'actual_yuan':str(actual),'expected_yuan':str(expected),'cell':row.get('key')})
        period=str(row.get('period',''));scope=str(row.get('scope','')).strip();scale=numeric(row.get('scale') or 0)
        meta=scope in ['合并','consolidated','Consolidated'] and re.search(r'(?<!\d)'+rule['period']+r'(?!\d)',period) and scale>0
        fact_meta_ok[id]=add('source_context:'+id,'R1',bool(meta),{'scope':scope,'period':period,'scale':str(scale),'required_period':rule['period']})
        pages={int(p) for p in re.findall(r'\d+',str(row.get('page','')))}
        fact_page_ok[id]=add('source_pages:'+id,'R1',bool(pages) and pages<=set(rule['pages']),{'declared':sorted(pages),'supporting':rule['pages']})
        if row:leaves.update(b.leaves(row['key']))
    gold={id:Decimal(v['value']) for id,v in defs['facts'].items()};gold_metrics=calculate(gold,defs['bridge_codes'],defs['groups'])
    for id,rule in defs['metrics'].items():
        row=index.get(id,{});actual=values.get(id);expected=gold_metrics[id];tol=Decimal('0.000001') if id.startswith('RATIO') else Decimal('.02')
        formula=bool(row and b.cells.get(row['key'],{}).get('formula'))
        ok=actual is not None and abs(actual-expected)<=tol and (not rule['require_formula'] or formula)
        metric_ok[id]=add('metric:'+id,'numeric',ok,{'actual':str(actual),'expected':str(expected),'tolerance':str(tol),'cell':row.get('key'),'index_formula':formula,'formula_required':rule['require_formula']})
    # Recompute all outputs under two distinct perturbation vectors. Gold figures
    # never substitute for workbook calculations. Source values for each scenario
    # are read back from the perturbed workbook, supporting reconstructed facts.
    if len(present)==len(defs['facts'])+len(defs['metrics']):
        for run in [1,2]:
            overrides={}
            for key in sorted(leaves):
                seed=int(hashlib.sha256((str(run)+str(key)).encode()).hexdigest()[:8],16)
                delta=Decimal(seed%2001-1000)/100
                overrides[key]=numeric(b.raw(key))+delta
            b.reset(overrides);vals=evaluate_values(present)
            pert_facts={id:vals[id] for id in defs['facts']};want=calculate(pert_facts,defs['bridge_codes'],defs['groups'])
            for id,rule in defs['metrics'].items():
                if not rule['require_formula']:continue
                tol=Decimal('0.000001') if id.startswith('RATIO') else Decimal('.02')
                good=abs(vals[id]-want[id])<=tol
                add('sensitivity_'+str(run)+':'+id,'formula_sensitivity',good,{'actual':str(vals[id]),'expected_from_perturbed_sources':str(want[id]),'input_leaf_count':len(overrides)})
                metric_ok[id]=metric_ok[id] and good
        b.reset()
        # Single-factor CFO tests ensure every bridge line is materially linked,
        # including NP facts entered directly, with no layout assumptions.
        for y,suffix in [(2024,'24'),(2025,'25')]:
            for code in defs['bridge_codes']:
                source_id=code+'_'+str(y);raws=b.leaves(index[source_id]['key'])
                if not raws:
                    good=False;details={'reason':'source fact has no editable numeric input'}
                else:
                    overrides={k:numeric(b.raw(k))+Decimal('1.23') for k in raws}
                    b.reset(overrides)
                    ids=list(defs['facts'])+['CFO'+suffix];vals=evaluate_values(ids)
                    want=calculate({id:vals[id] for id in defs['facts']},defs['bridge_codes'],defs['groups'])['CFO'+suffix]
                    good=abs(vals['CFO'+suffix]-want)<=Decimal('.02');details={'actual':str(vals['CFO'+suffix]),'expected':str(want),'perturbed_fact':source_id,'leaf_cells':[str(k) for k in sorted(raws)]}
                add('cfo_single_source:'+source_id,'R2',good,details);metric_ok['CFO'+suffix] &= good;b.reset()
    else:
        for id,rule in defs['metrics'].items():
            if rule['require_formula']:metric_ok[id]=False
        add('sensitivity_prerequisites','R2',False,{'missing_ids':[id for id in list(defs['facts'])+list(defs['metrics']) if id not in index]})
    def fraction(mapping,ids=None):
        ids=list(ids or mapping);return sum(bool(mapping.get(i)) for i in ids)/len(ids) if ids else 0
    def points(id,maxpoints,score,detail):criteria.append({'criterion_id':id,'maximum_points':maxpoints,'points_awarded':round(score,6),'status':'passed' if abs(score-maxpoints)<1e-5 else 'failed','detail':detail})
    points('R1',20,12*fraction(fact_value_ok)+5*fraction(fact_meta_ok)+3*fraction(fact_page_ok),'72 source amounts, period/scope/scaling and supported pages')
    controls=[id for id in defs['metrics'] if '_CONTROL' in id]
    other2=['RATIO24','RATIO25','SPREAD24','SPREAD25','CFO_DELTA','NP_DELTA']
    points('R2',25,12*fraction(metric_ok,['CFO24','CFO25'])+8*fraction(metric_ok,other2)+5*fraction(metric_ok,[id for id in controls if not id.startswith(('INV','AR','CL'))]),'recalculated CFO and complete single-source sensitivities, metrics and independent controls')
    contrib=[c+'_CONTRIB' for c in defs['bridge_codes']];groupok={}
    for c in defs['bridge_codes']:
        row=index.get(c+'_CONTRIB',{});declared=str(row.get('group',''));wanted=defs['groups'][c]
        groupok[c]=add('group:'+c,'R3',declared==wanted or (wanted=='非营运资本调整' and declared.startswith(wanted)),{'declared':declared,'required_class':wanted})
    top=sorted(defs['bridge_codes'],key=lambda c:abs(gold_metrics[c+'_CONTRIB']),reverse=True)[:3]
    rankok={}
    for rank,c in enumerate(top,1):
        val=index.get(c+'_CONTRIB',{}).get('rank')
        try:rank_matches=numeric(val)==Decimal(rank)
        except FormulaError:rank_matches=False
        rankok[c]=add('rank:'+c,'R3',rank_matches,{'declared':str(val),'required':rank})
    points('R3',15,10*fraction(metric_ok,contrib+['WC_DELTA','NONWC_DELTA','CONTRIB_CONTROL'])+3*fraction(groupok)+2*fraction(rankok),'all 17 arithmetic contributions, grouping and absolute ranking')
    inv=[id for id in defs['metrics'] if id.startswith('INV')]
    points('R4',10,10*fraction(metric_ok,inv),'inventory gross/net/provision arithmetic, residuals, formulas and perturbed inputs')
    wc=[id for id in defs['metrics'] if id.startswith(('AR_','AP_','CL_'))]
    points('R5',8,8*fraction(metric_ok,wc),'AR/AP scope residual arithmetic and CL components, formulas and perturbed inputs')
    memo=memofile.read_text(encoding='utf-8') if memofile.is_file() else '';length=len(re.findall(r'[\u4e00-\u9fff]',memo))
    readable=memofile.is_file() and len(memo.strip())>=300
    add('memo_readable','R6',readable,{'chinese_characters':length,'recommended': '800–1500','semantic_content':'requires actual external review'})
    points('R6',2,(1 if readable else 0)+(1 if tables and not duplicates else 0),'readable memo and discoverable nonambiguous handoff index; rhetorical quality is manual')
    semantic=[{'criterion_id':id,**rule,'status':'pending_external_review','points_awarded':0,'reason':'自由投研论证须实际阅读当前产物；自动数值通过不替代语义判定。'} for id,rule in MANUAL.items()]
    auto=sum(c['points_awarded'] for c in criteria);manual=sum(c['points_awarded'] for c in semantic);pending=sum(c['points'] for c in semantic if c['status']=='pending_external_review')
    return {'status':'passed' if auto>=79.99999 and pending==0 and manual==20 else 'automatic_pass_semantics_pending' if auto>=79.99999 and pending else 'failed','reward':round((auto+manual)/100,6),'automatic_points':round(auto,6),'semantic_points':manual,'pending_semantic_points':pending,'maximum_points':100,'artifact_hashes':hashes,'criteria':criteria,'semantic_criteria':semantic,'checks':checks,'formula_engines':engines or [{'engine':'Decimal XLSX formula interpreter','supported':'arithmetic, cross-sheet/absolute/ranges, shared formulas, named ranges, SUM, SUMPRODUCT, PRODUCT, ABS, MIN/MAX, AVERAGE, ROUND, INDEX/MATCH, IF/IFERROR, AND/OR; native LibreOffice fallback'}], 'coverage_limits':['Free prose financial causality and evidence boundaries are external M1–M4, never keyword or reference-text matching.','XLSX index discovery is based on public business fields; any sheet names, columns, rows and formula layouts are accepted.','Unchanged original fact values including consolidated NP may be raw values; derived outputs require true recalculation and input sensitivity.']}

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',default='/workspace/output');p.add_argument('--expectations',default=str(Path(__file__).with_name('expectations.json')));p.add_argument('--logs',default='/logs/verifier');a=p.parse_args();logs=Path(a.logs);logs.mkdir(parents=True,exist_ok=True)
    (logs/'reward.txt').unlink(missing_ok=True);(logs/'reward.json').unlink(missing_ok=True)
    (logs/'report.json').write_text('{"status":"verifier_failure","valid":false,"reward":null,"error":"objective verifier did not finish"}\n')
    try:report=evaluate(a.output,a.expectations);report['valid']=True;report['scope']='objective_core_only'
    except Exception as e:report={'status':'verifier_failure','valid':False,'reward':None,'error':type(e).__name__+': '+str(e),'criteria':[],'checks':[{'check_id':'verifier_exception','status':'failed','details':str(e)}]}
    (logs/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    if report['valid']:(logs/'reward.txt').write_text(str(report['reward'])+'\n')
    print(json.dumps({k:report.get(k) for k in ['status','reward','automatic_points','semantic_points','pending_semantic_points']},ensure_ascii=False))
    return 0 if report['valid'] else 1
if __name__=='__main__':raise SystemExit(main())
