#!/usr/bin/env python3
"""File/schema, fixed record dates/parties and recorded disposition only.

This program does not determine legal adequacy, chemistry, truth of free text,
or whether a citation actually supports the conclusion. Those need the judge.
"""
import csv
import json
import re
import sys
from datetime import date
from pathlib import Path

TASK = Path(__file__).resolve().parent.parent


def inspect(output_dir, input_dir=None):
    output_dir=Path(output_dir)
    if input_dir is None:
        live=Path('/workspace/input-data')
        input_dir=live if live.is_dir() else TASK/'environment/input-data'
    schema=json.loads((Path(input_dir)/'csv-schema.json').read_text(encoding='utf-8'))
    checks=[]
    def check(id_,passed,expected,actual,reason):
        checks.append({'id':id_,'passed':bool(passed),'expected':expected,'actual':actual,'reason':reason})
    def load(name,fields):
        p=output_dir/name
        check(name+'.exists',p.is_file(),'file',p.is_file(),'Required deliverable exists')
        if not p.is_file(): return []
        try:
            with p.open(encoding='utf-8-sig',newline='') as f:
                r=csv.DictReader(f)
                headers=r.fieldnames or []
                ok=set(headers)==set(fields) and len(headers)==len(fields)
                check(name+'.headers',ok,fields,headers,'Same field set required; column order may differ')
                if not ok:return []
                rows=list(r)
            check(name+'.utf8_csv',True,'UTF-8 CSV','parsed','BOM and no BOM accepted')
            return rows
        except (UnicodeError,csv.Error,OSError) as exc:
            check(name+'.utf8_csv',False,'UTF-8 CSV',str(exc),'Could not parse delivered CSV')
            return []
    def valid_pages(s):
        ts=re.split(r'[;,]',str(s).strip())
        return bool(ts) and all(re.fullmatch(r'\d+',t.strip()) and 1<=int(t.strip())<=18 for t in ts)
    def valid_precision(value,precision):
        patterns={'day':r'\d{4}-\d{2}-\d{2}','month':r'\d{4}-\d{2}','year':r'\d{4}'}
        if precision not in patterns:return not value
        if not re.fullmatch(patterns[precision],value):return False
        try:
            date.fromisoformat(value+{'day':'','month':'-01','year':'-01-01'}[precision]); return True
        except ValueError:return False

    spec=schema['evidence_ledger']
    rows=load('evidence-ledger.csv',spec['fields'])
    ids=[r.get('evidence_id','') for r in rows]
    required=set(spec['required_ids'])
    check('ledger.ids',len(ids)==36 and set(ids)==required,'36 unique specified IDs',ids,'Document coverage and no duplicate IDs')
    by_id={r.get('evidence_id'):r for r in rows}
    for r in rows:
        id_=r.get('evidence_id','')
        empty=[k for k in spec['required_nonempty_fields'] if not str(r.get(k) or '').strip()]
        invalid=[k for k,vs in spec['enums'].items() if r.get(k) not in vs]
        check(id_+'.fields',not empty and not invalid,{'required_nonempty_fields':spec['required_nonempty_fields'],'valid_enums':True},{'empty_required_fields':empty,'invalid_enums':invalid},'Schema conformance only; unknown narrative fields may be blank. The judge checks whether a claimed gap is supported.')
        value=r.get('publication_date','') or ''; precision=r.get('date_precision','')
        check(id_+'.date_precision',valid_precision(value,precision),precision,value,'Date has matching precision and valid calendar form')
        expected='2024-04-28' if id_.startswith('C') else ('2024-03-08' if id_ in ['E14','E15','E16'] else '2024-02-08')
        check(id_+'.first_submitted_on',r.get('first_submitted_on')==expected,expected,r.get('first_submitted_on'),'First submission in L044 p4–7; later corrections do not change it')
        presenter='专利权人' if id_.startswith('C') else '请求人'
        check(id_+'.presenter',r.get('presenter')==presenter,presenter,r.get('presenter'),'Submitting party in decision record')
        check(id_+'.pages',valid_pages(r.get('decision_pages','')),'physical pages1–18',r.get('decision_pages'),'Only checks existence range; support for conclusion needs professional review')
    dates={'E1':('','not_stated'),'E2':('2007-06-14','day'),'E3':('2023-12-05','day'),'E4':('2021-11-11','day'),'E5':('2022-03-08','day'),'E6':('1986','year'),'E7':('2006-11-30','day'),'E8':('1977-01','month'),'E9':('','not_stated'),'E10':('','not_stated'),'E11':('','not_stated'),'E12':('','not_stated'),'E13':('2006-08-17','day'),'E14':('1981-01','month'),'E15':('1998-10','month'),'E16':('2002-05','month'),'C1':('','not_stated'),'C2-1':('2004','year'),'C2-2':('1994-07','month'),'C2-3':('','not_stated'),'C2-4':('2002','year'),'C2-5':('1997-11-15','day'),'C2-6':('2002','year'),'C2-7':('2003','year'),'C2-8':('1997-12','month'),'C2-9':('2000','year'),'C2-10':('2000','year'),'C2-11':('2002','year'),'C2-12':('2000','year'),'C2-13':('2003','year'),'C2-14':('2003','year'),'C2-15':('2005-04','month'),'C2-16':('2005-01','month'),'C2-17':('2004','year'),'C2-18':('','not_stated'),'C3':('','not_stated')}
    for id_,expected in dates.items():
        if id_ not in by_id: continue
        r=by_id[id_]; actual=(r.get('publication_date'),r.get('date_precision'))
        # E16 records a May edition and July printing. Either is defensible if
        # the narrative preserves the distinction; the judge checks that text.
        ok=actual==expected or (id_=='E16' and actual==('2002-07','month'))
        # Empty unknown publication date may use not_applicable for unpublished
        # procedural material; its semantic suitability is left to the judge.
        ok=ok or (expected[0]=='' and actual==('','not_applicable'))
        check(id_+'.explicit_publication_record',ok,expected,actual,'Date/precision recorded in L044 p4–7; application/submission dates belong elsewhere')
    for id_,k,expected in [('E2','prior_art_status','not_prior_art'),('E2','citation_status','accepted_in_this_issue'),('E3','prior_art_status','withdrawn'),('E3','citation_status','withdrawn')]:
        if id_ in by_id:
            actual=by_id[id_].get(k)
            check(id_+'.'+k,actual==expected,expected,actual,'Field records decision disposition; conditional disagreement belongs in analysis')

    args=load('argument-comparison.csv',schema['argument_comparison']['fields'])
    issueids=[r.get('issue_id','') for r in args]
    check('arguments.ids',bool(issueids) and all(issueids) and len(set(issueids))==len(issueids),'nonempty unique issue IDs',issueids,'No fixed issue-row count; professional coverage judged separately')
    for r in args:
        id_=r.get('issue_id','')
        required_fields=schema['argument_comparison']['required_nonempty_fields']
        empty=[k for k in required_fields if not str(r.get(k) or '').strip()]
        check(id_+'.fields',not empty,required_fields,empty,'Core issue, review and locators required; unreported positions may be blank. Legal coverage is judged separately.')
        check(id_+'.pages',valid_pages(r.get('decision_pages','')),'physical pages1–18',r.get('decision_pages'),'Actual source page range')
        linked={t.strip() for t in re.split(r'[;,]',r.get('linked_evidence_ids',''))}
        check(id_+'.evidence_links',linked<=required,'provided evidence IDs',sorted(linked),'Stable cross-reference identifiers')
    memo=output_dir/'team-review.md'
    try:
        content=memo.read_text(encoding='utf-8')
        check('memo.utf8_nonempty',bool(content.strip()),'nonempty UTF-8 Markdown',{'bytes':memo.stat().st_size},'No keyword or full-text correctness matching')
    except (UnicodeError,OSError) as exc:
        check('memo.utf8_nonempty',False,'nonempty UTF-8 Markdown',str(exc),'Required memo readable')
    errors=[{'id':c['id'],'expected':c['expected'],'actual':c['actual'],'reason':c['reason']} for c in checks if not c['passed']]
    return {'status':'failed' if errors else 'passed','checks':checks,'errors':errors,'scope':'objective only','facts':{'ledger_rows':len(rows),'argument_rows':len(args),'professional_reasoning':'not evaluated'}}


if __name__=='__main__':
    result=inspect(sys.argv[1] if len(sys.argv)>1 else '/workspace/output')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(0 if result['status']=='passed' else 1)
