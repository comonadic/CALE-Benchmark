#!/usr/bin/env python3
"""Structured local authoring checker. Professional reasoning remains rubric/manual.

Reads public scenario inputs and native DOCX tables, not private gold outputs.
Usage: python3 check_outputs.py --output-dir DIRECTORY [--report FILE]
"""
import argparse, csv, html, json, math, re, zipfile
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET

TASK=Path(__file__).resolve().parent.parent
INPUT=Path(__file__).resolve().parent/'input-data'

def readcsv(name):
    with (INPUT/name).open(encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))
def number(x): return Decimal(str(x))

def check(out):
    errors=[]; assertions=[]
    def fail(c,where,msg):
        errors.append(dict(criterion=c,object=where,message=msg))
        if not any(a['criterion']==c and a['object']==where and not a['passed'] for a in assertions): assertions.append(dict(criterion=c,object=where,passed=False,expected='valid structured relationship',received=msg))
    def equal(c,where,got,expected,tol=Decimal('0')):
        if isinstance(expected,bool): ok=type(got) is bool and got==expected
        elif isinstance(expected,(int,float,Decimal)):
            try: ok=not isinstance(got,bool) and isinstance(got,(int,float)) and math.isfinite(got) and abs(number(got)-number(expected))<=tol
            except Exception: ok=False
        else: ok=got==expected
        assertions.append(dict(criterion=c,object=where,passed=ok,expected=str(expected) if isinstance(expected,Decimal) else expected,received=got))
        if not ok: fail(c,where,f'expected {expected!s}; received {got!s}')
    def index(section,key,ids):
        items=j.get(section,[])
        if not isinstance(items,list): fail('R7',section,'must be array'); return {}
        result={}
        for item in items:
            if not isinstance(item,dict) or key not in item: fail('R7',section,f'missing {key}'); continue
            if item[key] in result: fail('R7',section,'duplicate object id')
            result[item[key]]=item
        for rid in ids:
            if rid not in result: fail('R7',section,f'missing {rid}')
        return result
    try: j=json.loads((out/'funding_results.json').read_text())
    except Exception as e: return dict(status='failed',errors=[dict(criterion='R7',object='funding_results.json',message=str(e))],manual_review_required=True)
    ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    xml=ET.fromstring(zipfile.ZipFile(INPUT/'F047-original.docx').read('word/document.xml'))
    tables=xml.findall('.//w:body/w:tbl',ns)
    cells=lambda row:[''.join(t.text or '' for t in c.findall('.//w:t',ns)) for c in row.findall('w:tc',ns)]
    rates=[number(cells(row)[1].rstrip('%'))/100 for row in tables[0].findall('w:tr',ns)[1:]]
    limits=[int(x) for x in cells(tables[1].findall('w:tr',ns)[3])[1:]]
    # Native clause confirms 15kg. Extraction fails closed if expected normative text differs.
    native=''.join(x.text or '' for x in xml.findall('.//w:t',ns))
    if '交易单位为15千克/手' not in native: raise ValueError('native multiplier source changed')
    multiplier=number(re.search(r'交易单位为([0-9]+)千克/手',native).group(1))
    cal=readcsv('planning_calendar.csv'); trading=[r['date'] for r in cal if r['is_trading_day']=='1']; working=[r['date'] for r in cal if r['is_working_day']=='1']
    month='2026-12'; prevmonth='2026-11'; prevdays=[d for d in trading if d.startswith(prevmonth)]; deldays=[d for d in trading if d.startswith(month)]
    futlast=next(d for d in deldays if d>=month+'-15'); stage20=[d for d in trading if d<futlast][-2]; expiry=prevdays[-5]
    dates=dict(option_expiry_date=expiry,option_expiry_exercise_cutoff=expiry+'T15:30:00+08:00',futures_last_trading_date=futlast,delivery_dates=[d for d in working if d>futlast][:2],margin_20pct_start_date=stage20)
    actual=j.get('contract_timeline',{})
    for k,v in dates.items():
        got=actual.get(k)
        if k=='option_expiry_exercise_cutoff':
            try: got=datetime.fromisoformat(got).astimezone(timezone.utc).isoformat(); v=datetime.fromisoformat(v).astimezone(timezone.utc).isoformat()
            except Exception: pass
        equal('R3','timeline.'+k,got,v)
    equal('R7','metadata.currency',j.get('metadata',{}).get('currency'),'CNY')
    raw=readcsv('futures_snapshots.csv'); ri={x['row_id']:x for x in raw}; fi=index('futures_snapshots','row_id',ri)
    expected={}
    for rid,r in ri.items():
        dt=r['snapshot_date']; stage=int(dt>=prevdays[0])+int(dt>=deldays[0]); rate=rates[3] if dt>=stage20 else rates[stage]
        offset=1 if r['participant_type']=='customer' else 0; limit=limits[stage*2+offset]
        l,s=int(r['long_lots']),int(r['short_lots']); p,prev,eq0=map(number,[r['settlement_cny_per_kg'],r['previous_settlement_cny_per_kg'],r['equity_before_vm_cny']])
        vm=(l-s)*(p-prev)*multiplier; eq=eq0+vm; margin=(l+s)*p*multiplier*rate
        exp=dict(margin_rate=rate,directional_limit_lots=limit,long_lots=l,short_lots=s,long_excess_lots=max(l-limit,0),short_excess_lots=max(s-limit,0),parity_required=dt>=prevdays[-1],parity_compliant=(dt<prevdays[-1] or l%2==0 and s%2==0),variation_margin_cny=vm,equity_after_vm_cny=eq,required_margin_cny=margin,additional_funds_cny=max(margin-eq,0))
        expected[rid]=exp; got=fi.get(rid,{})
        for k,v in exp.items(): equal('R2' if k in ['directional_limit_lots','long_lots','short_lots','long_excess_lots','short_excess_lots','parity_required','parity_compliant'] else 'R1',rid+'.'+k,got.get(k),v,Decimal('.01') if k.endswith('_cny') else (Decimal('1e-9') if k=='margin_rate' else Decimal('0')))
        if not got.get('calculation_trace'): fail('R7',rid,'missing nonempty calculation_trace; manual evaluator checks its actual formulas')
    events=readcsv('option_requests.csv'); oi=index('option_requests','event_id',[e['event_id'] for e in events]); effects={}
    for e in events:
        dt=e['request_at'][:10]; clock=e['request_at'][11:19]; qty=int(e['quantity_lots']); inventory=int(e['available_lots'])
        valid=dt in trading and dt<=expiry and 0<qty<=inventory and ((dt==expiry and clock<'15:30:00') or (dt<expiry and ('09:00:00'<=clock<='11:30:00' or '13:30:00'<=clock<='15:00:00')))
        disp=e['request'] if valid else 'reject'; l=qty if disp=='exercise' and e['option_type']=='call' else 0; s=qty if disp=='exercise' and e['option_type']=='put' else 0
        vm=(l-s)*(number(ri[e['base_row_id']]['settlement_cny_per_kg'])-number(e['strike_cny_per_kg']))*multiplier
        exp=dict(time_and_inventory_valid=valid,request_disposition=disp,added_long_lots=l,added_short_lots=s,incremental_vm_cny=vm); effects[e['event_id']]=exp
        for k,v in exp.items(): equal('R4',e['event_id']+'.'+k,oi.get(e['event_id'],{}).get(k),v,Decimal('.01') if k.endswith('_cny') else Decimal('0'))
    pi=index('post_option_snapshots','base_row_id',['R03','R11'])
    for rid in ['R03','R11']:
        allids=[e['event_id'] for e in events if e['base_row_id']==rid]; ids=[eid for eid in allids if effects[eid]['request_disposition']=='exercise']; b=expected[rid]
        l=b['long_lots']+sum(effects[eid]['added_long_lots'] for eid in ids); s=b['short_lots']+sum(effects[eid]['added_short_lots'] for eid in ids); inc=sum((effects[eid]['incremental_vm_cny'] for eid in ids),Decimal(0)); eq=b['equity_after_vm_cny']+inc; m=(l+s)*number(ri[rid]['settlement_cny_per_kg'])*multiplier*b['margin_rate']
        exp=dict(long_lots=l,short_lots=s,long_excess_lots=max(l-b['directional_limit_lots'],0),short_excess_lots=max(s-b['directional_limit_lots'],0),incremental_vm_cny=inc,equity_after_vm_cny=eq,required_margin_cny=m,additional_funds_cny=max(m-eq,0))
        got=pi.get(rid,{})
        for k,v in exp.items(): equal('R4',rid+'.post.'+k,got.get(k),v,Decimal('.01') if k.endswith('_cny') else Decimal('0'))
        applied=got.get('applied_event_ids',[])
        valid_zero=[eid for eid in allids if effects[eid]['request_disposition']=='abandon']
        if not isinstance(applied,list) or len(applied)!=len(set(applied)) or set(applied)-set(ids+valid_zero) or set(ids)-set(applied): fail('R4',rid+'.applied_event_ids','must include all valid exercises; optional zero-effect valid abandonment permitted; rejected events excluded')
        if not got.get('calculation_trace'): fail('R7',rid+'.post','missing calculation_trace')
    plans=readcsv('proposed_trade_plans.csv'); ti=index('trade_plan_checks','plan_id',[p['plan_id'] for p in plans])
    for p in plans:
        b=expected[p['base_row_id']]; qs=[int(p[k]) for k in ['open_long_lots','open_short_lots','close_long_lots','close_short_lots']]; l=b['long_lots']+qs[0]-qs[2]; s=b['short_lots']+qs[1]-qs[3]
        exp=dict(transaction_lot_parity_valid=(p['submitted_at'][:7]!=month or all(q%2==0 for q in qs)),resulting_long_lots=l,resulting_short_lots=s,resulting_long_excess_lots=max(l-b['directional_limit_lots'],0),resulting_short_excess_lots=max(s-b['directional_limit_lots'],0),resulting_position_parity_valid=(not b['parity_required'] or l%2==0 and s%2==0))
        for k,v in exp.items(): equal('R5',p['plan_id']+'.'+k,ti.get(p['plan_id'],{}).get(k),v)
        # Disposition wording/funding operational holds are intentionally manual.
        if not ti.get(p['plan_id'],{}).get('reason'): fail('R7',p['plan_id'],'missing plan reason')
    quote_rows=readcsv('proposed_option_quotes.csv'); qi=index('quote_checks','quote_id',[q['quote_id'] for q in quote_rows])
    option_html=(INPUT/'F042-original.html').read_text()
    contract_rows={}
    for tr in re.findall(r'<tr[^>]*>(.*?)</tr>',option_html,re.S|re.I):
        tds=[html.unescape(re.sub(r'<[^>]+>','',td)).strip() for td in re.findall(r'<td[^>]*>(.*?)</td>',tr,re.S|re.I)]
        if len(tds)>=2: contract_rows[tds[0]]=tds[1]
    tick=number(re.search(r'[0-9.]+',contract_rows['最小变动价位']).group())
    for q in quote_rows:
        premium=number(q['premium_cny_per_kg']); qty=int(q['quantity_lots']); lower=(premium//tick)*tick; upper=lower if premium%tick==0 else lower+tick
        exp=dict(tick_valid=(premium%tick==0),one_lot_tick_value_cny=tick*multiplier,quoted_quantity_tick_value_cny=qty*tick*multiplier,nearest_lower_valid_quote=lower,nearest_upper_valid_quote=upper)
        for k,v in exp.items(): equal('R6',q['quote_id']+'.'+k,qi.get(q['quote_id'],{}).get(k),v,Decimal('.01'))
    try:
        with (out/'risk_ledger.csv').open(encoding='utf-8-sig',newline='') as f:
            ledger=list(csv.DictReader(f))
        required={'object_id','object_type','assessment','severity','rule_locator','corrective_action','due_at'}
        if not ledger or required-set(ledger[0]): fail('R7','risk_ledger.csv','missing required columns or rows')
        for oid in set(ri)|{e['event_id'] for e in events}|{p['plan_id'] for p in plans}|{'Q01'}:
            matching=[r for r in ledger if r.get('object_id')==oid]
            if not matching: fail('R7','risk_ledger.csv',f'missing object {oid}')
            elif any(not r.get(k,'').strip() for r in matching for k in required): fail('R7',oid,'empty ledger required field')
        if len([r for r in ledger if r.get('object_type')=='timeline'])<4: fail('R7','risk_ledger.csv','four timeline rows expected; manual reviewer assesses correct deadline facts')
    except Exception as e: fail('R7','risk_ledger.csv',str(e))
    try:
        if len((out/'action_memo.md').read_text().strip())<80: fail('R7','action_memo.md','missing usable memo')
    except Exception as e: fail('R7','action_memo.md',str(e))
    return dict(status='passed' if not errors else 'failed',assertions=assertions,errors=errors,manual_review_required=True,completed=True,scope='Arithmetic, calendar, structured fields and object coverage only. Does not grade professional explanation or grant trading permission.')

if __name__=='__main__':
    a=argparse.ArgumentParser(); a.add_argument('--output-dir',required=True,type=Path); a.add_argument('--report',type=Path); args=a.parse_args()
    result=check(args.output_dir)
    if args.report: args.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2)); raise SystemExit(0 if result['status']=='passed' else 1)
