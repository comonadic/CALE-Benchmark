"""Weighted objective fiscal ledger checks. Free prose is independently adjudicated."""
import csv,hashlib,json
from decimal import Decimal,InvalidOperation
from pathlib import Path

HERE=Path(__file__).resolve().parent
class CandidateCSVError(ValueError): pass
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load_csv(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f,strict=True);fields=reader.fieldnames or [];rows=list(reader)
    if len(set(fields))!=len(fields):raise CandidateCSVError('Duplicate CSV header cannot be unambiguously extracted')
    if any(None in row for row in rows):raise CandidateCSVError('CSV row has more values than declared columns')
    return fields,rows
def evaluate(path):
    facts=json.loads((HERE/'expectations.json').read_text())
    fields,rows=load_csv(path);by={};duplicates=[];assertions=[]
    def add(c,key,passed,actual,expected,detail):
        assertions.append({'criterion':c,'assertion_id':key,'passed':bool(passed),'actual':actual,'expected':expected,'detail':detail})
    for row in rows:
        item=row.get('item_id','').strip()
        if item in by:duplicates.append(item)
        by[item]=row
    add('A01','unique_ids',not duplicates and '' not in by,duplicates,'unique nonempty IDs','Core IDs preserve a stable handoff key; row order is unrestricted.')
    for field in facts['required_columns']:add('A01','column:'+field,field in fields,field,'required','Only interoperability fields are required; added columns accepted.')
    for item in facts['core_ids']:
        add('A01','row:'+item,item in by,item,'present','Required issue coverage.')
        row=by.get(item,{})
        for field in ['title','scope','period','role','source_locator','calculation','evidence_limit','next_evidence']:
            add('A01',f'{item}:nonempty:{field}',bool(str(row.get(field,'')).strip()),row.get(field,''),'nonempty','Presence only; accuracy and professional value belong to independent rubric.')
        add('A01',f'{item}:priority',row.get('priority') in ['high','medium','low'],row.get('priority'),'high/medium/low','Priority meaning independently reviewed.')
        for field,(target,tolerance) in facts['numeric'][item].items():
            group='A02' if field in ['original_value','original_yiyuan','progress_value','progress_yiyuan'] else 'A03'
            if item=='R01':group='A04'
            try:
                actual=Decimal(row.get(field,''));expected=Decimal(str(target));tol=Decimal(str(tolerance));ok=actual.is_finite() and abs(actual-expected)<=tol
            except (InvalidOperation,ValueError,TypeError):ok=False
            add(group,f'{item}:{field}',ok,row.get(field,''),{'value':target,'absolute_tolerance':tolerance},'Source-specific amount, count or percentage precision.')
        for field in facts['blank'].get(item,[]):
            add('A03' if item=='O01' else 'A05',f'{item}:unknown:{field}',not str(row.get(field,'')).strip(),row.get(field,''),'blank','Absent disclosure or non-applicability is distinct from an observed zero.')
        if item=='O01':
            value=str(row.get('completed_count','')).strip()
            try:ok=not value or Decimal(value)==Decimal('2124')
            except InvalidOperation:ok=False
            add('A03','O01:completed_count_role',ok,value,'blank or2124 as a potentially valid conditional complement; actual assumption/role reviewed independently','A blank confirmed count or a conditional2124 is numerically possible. Independent M02 must reject any claim that2124 is a confirmed source actual or that98% determines an exact integer.')
            value=str(row.get('other_count','')).strip()
            try:ok=not value or Decimal(value)==Decimal('62')
            except InvalidOperation:ok=False
            add('A02','O01:optional_outstanding_count',ok,value,'blank or62 with its p22 disclosed role made clear','A reported outstanding count may be stored in this existing column, optional columns, text or auxiliary rows. Professional review verifies the actual cutoff/category meaning.')
            for field,rule in facts.get('optional_o01_numeric',{}).items():
                value=str(row.get(field,'')).strip()
                if not value:continue
                expected,tol=rule
                try:actual=Decimal(value);ok=actual.is_finite() and abs(actual-Decimal(str(expected)))<=Decimal(str(tol))
                except InvalidOperation:ok=False
                add('A02' if field.startswith('reported_') else 'A03',f'O01:optional:{field}',ok,value,{'value':expected,'absolute_tolerance':tol},'Optional business numeric column only if used; equivalent prose or auxiliary rows are permitted and reviewed against the actual sources.')
        for field,allowed,group in [('mapping_type',facts['mapping'][item],'A04'),('status',facts['statuses'][item],'A05'),('aggregation_rule',facts['aggregation'][item],'A04')]:
            add(group,f'{item}:{field}',row.get(field) in allowed,row.get(field),allowed,'Typed source relationship, disclosure state or aggregation policy; explanatory text independently reviewed.')
        if item in facts['units']:
            unit=row.get('original_unit','').split(' ')[0]
            add('A02',f'{item}:original_unit',unit in facts['units'][item],row.get('original_unit'),facts['units'][item],'Original monetary unit retained; annotation after a space allowed.')
        if item in facts.get('progress_units',{}):
            unit=row.get('progress_unit','').split(' ')[0]
            add('A02',f'{item}:progress_unit',unit in facts['progress_units'][item],row.get('progress_unit'),facts['progress_units'][item],'Progress quantity has the declared financial/count/percentage unit; annotation after a space allowed.')
    def relation(key,items,fn,expected,tolerance=0):
        try:
            vals=[Decimal(by[item][field]) for item,field in items];actual=fn(*vals);ok=actual.is_finite() and abs(actual-Decimal(str(expected)))<=Decimal(str(tolerance))
        except (KeyError,InvalidOperation,ValueError,TypeError,ZeroDivisionError):actual=None;ok=False
        add('A03',key,ok,str(actual) if actual is not None else None,expected,'Executable relationship on actual submitted fields.')
    relation('N01:gap_chain',[('N01','original_yiyuan'),('N01','progress_yiyuan'),('N01','disclosure_gap_yiyuan')],lambda a,b,c:a-b-c,0,.0001)
    relation('N02:gap_chain',[('N02','original_yiyuan'),('N02','progress_yiyuan'),('N02','disclosure_gap_yiyuan')],lambda a,b,c:a-b-c,0,.0001)
    for item in ['N01','N02']:
        relation(item+':coverage_chain',[(item,'progress_yiyuan'),(item,'original_yiyuan'),(item,'coverage_pct')],lambda a,b,c:a/b*100-c,0,.005)
    relation('N04:stage_partition',[('N04','started_count'),('N04','completed_count'),('N04','other_count'),('N04','total_count')],lambda a,b,c,t:a+b+c-t,0)
    relation('N04:complete_fraction',[('N04','completed_count'),('N04','total_count'),('N04','coverage_pct')],lambda a,b,c:a/b*100-c,0,.005)
    relation('N05:combined_partition',[('N05','progress_value'),('N05','other_count'),('N05','total_count')],lambda a,b,t:a+b-t,0)
    relation('N05:combined_fraction',[('N05','progress_value'),('N05','total_count'),('N05','coverage_pct')],lambda a,b,c:a/b*100-c,0,.005)
    relation('R01:submitted_component_sum',[('N01','progress_yiyuan'),('N02','progress_yiyuan'),('N03','progress_yiyuan'),('R01','progress_yiyuan')],lambda a,b,c,t:a+b+c-t,0,.0001)
    criteria=[]
    for c in facts['objective_criteria']:
        aa=[a for a in assertions if a['criterion']==c['id']];passed=sum(a['passed'] for a in aa);score=round(c['points']*passed/len(aa),6)
        criteria.append({'id':c['id'],'maximum_points':c['points'],'score':score,'passed_assertions':passed,'total_assertions':len(aa),'method':c['method']})
    return {'status':'passed' if all(a['passed'] for a in assertions) else 'graded_objective','automatic_points':round(sum(c['score'] for c in criteria),6),'automatic_points_available':60,'criteria':criteria,'assertions':assertions,'csv':{'columns':fields,'rows':rows},'professional_points_pending':40,'scope':'Objective relationships and typed business state only. Prose citation support, closure claims, follow-up usefulness and memo interpretation remain pending independent review.'}
