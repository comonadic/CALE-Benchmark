#!/usr/bin/env python3
import csv
import hashlib
import json
import re
import sys
from pathlib import Path
from decimal import Decimal
from pypdf import PdfReader

TESTS = Path('/tests')
CANDIDATE = Path('/workspace/output')
LOG = Path('/logs/verifier')
INPUT = Path('/tests/input-data/CN-1225248741_original.pdf')
EXPECTED_HASH = '18231670324fb8ab60c264dbaebf4972004a4c153aa5a046dc7be4d2e40646d9'
S = 24

FACTS = {
    ('2025','经营活动现金流入小计'): '3527194370.04',
    ('2024','经营活动现金流入小计'): '4134489117.69',
    ('2025','经营活动现金流出小计'): '3484208109.96',
    ('2024','经营活动现金流出小计'): '4125411208.51',
    ('2025','经营活动产生的现金流量净额'): '42986260.08',
    ('2024','经营活动产生的现金流量净额'): '9077909.18',
    ('2025','筹资活动现金流入小计'): '974280000.00',
    ('2024','筹资活动现金流入小计'): '914000000.00',
    ('2025','筹资活动现金流出小计'): '1100823838.67',
    ('2024','筹资活动现金流出小计'): '942903026.96',
    ('2025','筹资活动产生的现金流量净额'): '-126543838.67',
    ('2024','筹资活动产生的现金流量净额'): '-28903026.96',
    ('2025','现金及现金等价物净增加额'): '15613364.89',
    ('2024','现金及现金等价物净增加额'): '62431552.47',
    ('2025','经营性应收项目的减少（增加以“－”号填列）'): '33779318.53',
    ('2024','经营性应收项目的减少（增加以“－”号填列）'): '-30000712.68',
}


def status_row(aid, passed, actual, expected, criterion):
    return {'id': aid, 'status': 'passed' if passed else 'failed', 'actual': actual, 'expected': expected, 'criterion': criterion}


def parse_csv(path, required):
    with path.open(encoding='utf-8-sig', newline='') as f:
        rows=list(csv.DictReader(f))
    if not rows or not set(required).issubset(rows[0]):
        raise ValueError(f'{path.name}: missing required columns or rows')
    return rows


def dec(v):
    return Decimal(v.replace(',','').strip())


def main():
    LOG.mkdir(parents=True, exist_ok=True)
    for q in [LOG/'reward.json', LOG/'report.json']:
        q.unlink(missing_ok=True)
    try:
        if not INPUT.is_file() or hashlib.sha256(INPUT.read_bytes()).hexdigest() != EXPECTED_HASH:
            raise RuntimeError('trusted input missing or hash mismatch')
        reg = parse_csv(CANDIDATE/'evidence_register.csv', ['item_id','period','scope','line_item','reported_amount','unit','source_file','pdf_page','evidence_status','limitation'])
        gaps = parse_csv(CANDIDATE/'evidence_gaps.csv', ['gap_id','missing_evidence','why_needed','decision_blocked','next_action'])
        pdf = CANDIDATE/'misstatement_review.pdf'
        if not pdf.is_file() or pdf.stat().st_size < 1000:
            raise ValueError('misstatement_review.pdf missing or empty')
        by_key={(r['period'].strip(),r['line_item'].strip()):r for r in reg}
        rows=[]
        def has(period,label):
            r=by_key.get((period,label)); return r is not None
        def correct(period,label):
            r=by_key.get((period,label))
            return r is not None and dec(r['reported_amount']) == dec(FACTS[(period,label)])
        def loc(label):
            return any(r['line_item'].strip()==label and r['source_file'].strip()=='CN-1225248741_original.pdf' and r['pdf_page'].strip() in ('24','184') for r in reg)
        rows.append(status_row('E01', all(r['source_file'].strip()=='CN-1225248741_original.pdf' for r in reg), 'source_file values', 'visible source only', 'C1'))
        rows.append(status_row('E02', all(r['scope'].strip()=='合并' and r['period'].strip() in ('2025','2024') for r in reg), 'scope/period fields', '合并; 2025 and 2024', 'C1'))
        rows.append(status_row('E03', all(correct(y,l) for y in ('2025','2024') for l in ('经营活动现金流入小计','经营活动现金流出小计')), 'operating inflow/outflow', 'source values', 'C1'))
        rows.append(status_row('E04', all(correct(y,'经营活动产生的现金流量净额') for y in ('2025','2024')), 'operating net', 'source values', 'C1'))
        rows.append(status_row('E05', all(correct(y,l) for y in ('2025','2024') for l in ('筹资活动现金流入小计','筹资活动现金流出小计','筹资活动产生的现金流量净额')), 'financing values', 'source values', 'C1'))
        rows.append(status_row('E06', all(correct(y,'现金及现金等价物净增加额') for y in ('2025','2024')), 'cash change', 'source values', 'C1'))
        rows.append(status_row('E07', all(correct(y,'经营性应收项目的减少（增加以“－”号填列）') for y in ('2025','2024')), 'supplemental receivable changes', 'source values', 'C1'))
        rows.append(status_row('E08', all(loc(l) for l in ('经营活动现金流入小计','经营活动现金流出小计','经营活动产生的现金流量净额','筹资活动现金流入小计','筹资活动现金流出小计','筹资活动产生的现金流量净额','现金及现金等价物净增加额','经营性应收项目的减少（增加以“－”号填列）')), 'page locators', 'PDF 24 or 184', 'C1'))
        for y in ('2025','2024'):
            oi=dec(FACTS[(y,'经营活动现金流入小计')]); oo=dec(FACTS[(y,'经营活动现金流出小计')]); on=dec(FACTS[(y,'经营活动产生的现金流量净额')])
            fi=dec(FACTS[(y,'筹资活动现金流入小计')]); fo=dec(FACTS[(y,'筹资活动现金流出小计')]); fn=dec(FACTS[(y,'筹资活动产生的现金流量净额')])
            net=dec(FACTS[(y,'现金及现金等价物净增加额')])
            inv=Decimal('99170943.48') if y=='2025' else Decimal('82256670.25')
            rows.append(status_row('E09' if y=='2025' else 'E10', correct(y,'经营活动产生的现金流量净额') and oi-oo==on, f'{y}: inflow-outflow={oi-oo}', f'{y}: operating net={on}', 'C2'))
            rows.append(status_row('E11' if y=='2025' else 'E12', correct(y,'筹资活动产生的现金流量净额') and fi-fo==fn and on+inv+fn==net, f'{y}: financing and cross-activity arithmetic', f'{y}: reported totals reconcile', 'C2'))
        rows.append(status_row('E13', any('不是客户' in r['limitation'] or '审计调整' in r['limitation'] for r in reg) and (CANDIDATE/'misstatement_review.pdf').stat().st_size>1000, 'supplemental data limitation', 'not a ledger adjustment', 'C2'))
        required_gaps={'G01','G02','G03','G04','G05'}
        gapids={r['gap_id'].strip() for r in gaps}
        rows += [status_row('E14','G01' in gapids,'gap ids','G01', 'C3'), status_row('E15','G02' in gapids,'gap ids','G02','C3'), status_row('E16','G03' in gapids,'gap ids','G03','C3'), status_row('E17','G04' in gapids,'gap ids','G04','C3'), status_row('E18','G05' in gapids,'gap ids','G05','C3')]
        text=(CANDIDATE/'evidence_gaps.csv').read_text(encoding='utf-8-sig') + '\n' + (CANDIDATE/'evidence_register.csv').read_text(encoding='utf-8-sig')
        memo_path=CANDIDATE/'misstatement_review.pdf'
        memo_text=''.join(p.extract_text() or '' for p in PdfReader(memo_path).pages) if memo_path.is_file() else ''
        claim_phrases=['客户已入账','客户已过账','完成调整','完成审计程序','取得调整后试算平衡']
        claims=[]
        for phrase in claim_phrases:
            start=0
            while True:
                pos=(text+'\n'+memo_text).find(phrase,start)
                if pos < 0: break
                context=(text+'\n'+memo_text)[max(0,pos-18):pos+len(phrase)+8]
                if not any(neg in context for neg in ['不支持','不得','不能','尚未','缺少','无法']):
                    claims.append(context)
                start=pos+len(phrase)
        rows.append(status_row('E19', not claims, 'affirmative completion claim scan', 'no unsupported completed-work claim', 'C3'))
        rows.append(status_row('E20', all(r['evidence_status'].strip()=='公开披露事实' and r['limitation'].strip() for r in reg) and len(gaps)>=5, 'evidence status and limitations', 'public facts and limits explicit', 'C3'))
        memo_path=CANDIDATE/'misstatement_review.pdf'
        memo_bytes=memo_path.read_bytes()
        memo_text=''.join(p.extract_text() or '' for p in PdfReader(memo_path).pages)
        readable=len(memo_text)>600
        normalized_memo = re.sub(r'\s+', '', memo_text)
        rows.append(status_row('E21', readable and all(re.sub(r'\s+', '', x) in normalized_memo for x in ['范围','限制','PDF第24页','PDF第184页']), 'memo extracted text and citations', 'scope, limits, source locators', 'C4'))
        rows.append(status_row('E22', all(x in memo_text for x in ['试算平衡','过账','客户']), 'posting and TB procedures', 'trace management posting and request TB', 'C4'))
        rows.append(status_row('E23', all(x in memo_text for x in ['未更正错报','重要性','管理层']), 'aggregation and communication terms', 'evaluate and communicate uncorrected misstatements', 'C4'))
        rows.append(status_row('E24', len(reg)>=16 and len(gaps)>=5 and readable and all(x in memo_text for x in ['2025','2024','人民币元']), f'{len(reg)} evidence rows, {len(gaps)} gaps, {len(memo_bytes)} PDF bytes', 'three deliverables consistent', 'C5'))
        passed=sum(r['status']=='passed' for r in rows)
        reward=min(1.0, passed/S)
        caps=[]
        for ce, assertion, cap in [('CE.fake-ledger','E19',0.25),('CE.fake-posting','E16',0.5),('CE.wrong-entity','E02',0.5)]:
            if next(r for r in rows if r['id']==assertion)['status']=='failed':
                caps.append({'id':ce,'assertion':assertion,'cap':cap})
                reward=min(reward,cap)
        report={'status':'graded' if passed==S else 'graded_candidate_defect','valid':True,'P':passed,'S':S,'reward':reward,'assertions':rows,'critical_errors_triggered':caps}
        (LOG/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        (LOG/'reward.json').write_text(json.dumps({'reward':reward}),encoding='utf-8')
    except Exception as exc:
        report={'status':'verifier_failure','valid':False,'P':None,'S':S,'reward':None,'error':f'{type(exc).__name__}: {exc}','assertions':[]}
        (LOG/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        sys.exit(2)

if __name__=='__main__': main()
