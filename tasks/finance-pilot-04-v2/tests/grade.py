#!/usr/bin/env python3
"""Objective assertion grader for finance-pilot-04-v2.

Reads the candidate output directory, recomputes every expected value from
the trusted input copies, and scores reward = P / S over the assertions
declared in tests/assertions.json. No host bridge, no judge round-trip:
the whole reward is produced in this process.

Status vocabulary (see references/output-contract.md):
  graded                    complete valid scoring, reward written
  graded_candidate_defect   candidate artifacts missing/broken, scored as found
  verifier_failure          scoring dependency or protocol fault, NO reward
  not_run                   not executed
"""
import argparse
import csv
import hashlib
import html
import json
import re
import sys
import zipfile
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
TOL = Decimal('0.01')
TASK_ID = 'finance-pilot-04-v2'


# --------------------------------------------------------------------------
# trusted inputs
# --------------------------------------------------------------------------

def read_csv(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def read_rules(input_dir):
    """Normative values come from the attached originals, never from constants."""
    docx = Path(input_dir) / 'F047-original.docx'
    with zipfile.ZipFile(docx) as archive:
        document = ET.fromstring(archive.read('word/document.xml'))
    tables = document.findall(f'.//{{{W}}}body/{{{W}}}tbl')
    if len(tables) < 2:
        raise ValueError('normative tables missing from F047-original.docx')

    def cells(row):
        return [''.join(node.text or '' for node in cell.findall(f'.//{{{W}}}t'))
                for cell in row.findall(f'{{{W}}}tc')]

    rates = [Decimal(cells(row)[1].rstrip('%')) / 100 for row in tables[0].findall(f'{{{W}}}tr')[1:]]
    limit_rows = tables[1].findall(f'{{{W}}}tr')
    limits = [int(value) for value in cells(limit_rows[3])[1:]]

    native = ''.join(node.text or '' for node in document.findall(f'.//{{{W}}}t'))
    if '交易单位为15千克/手' not in native:
        raise ValueError('native multiplier source changed')
    multiplier = Decimal(re.search(r'交易单位为([0-9]+)千克/手', native).group(1))

    page = (Path(input_dir) / 'F042-original.html').read_text(encoding='utf-8')
    contract = {}
    for row in re.findall(r'<tr[^>]*>(.*?)</tr>', page, re.S | re.I):
        tds = [html.unescape(re.sub(r'<[^>]+>', '', td)).strip()
               for td in re.findall(r'<td[^>]*>(.*?)</td>', row, re.S | re.I)]
        if len(tds) >= 2:
            contract[tds[0]] = tds[1]
    tick = Decimal(re.search(r'[0-9.]+', contract['最小变动价位']).group())
    return {'rates': rates, 'limits': limits, 'multiplier': multiplier, 'tick': tick}


def read_calendar(input_dir):
    calendar = read_csv(Path(input_dir) / 'planning_calendar.csv')
    return {
        'trading': [row['date'] for row in calendar if row['is_trading_day'] == '1'],
        'working': [row['date'] for row in calendar if row['is_working_day'] == '1'],
    }


def derive_expectations(rules, calendar):
    """Every expected value, recomputed from the trusted inputs."""
    rates, limits, multiplier = rules['rates'], rules['limits'], rules['multiplier']
    tick = rules['tick']
    trading, working = calendar['trading'], calendar['working']
    prior_days = [day for day in trading if day.startswith('2026-11')]
    delivery_days = [day for day in trading if day.startswith('2026-12')]
    futures_last = next(day for day in delivery_days if day >= '2026-12-15')
    stage_20pct = [day for day in trading if day < futures_last][-2]
    expiry = prior_days[-5]

    timeline = {
        'option_expiry_date': expiry,
        'option_expiry_exercise_cutoff': expiry + 'T15:30:00+08:00',
        'futures_last_trading_date': futures_last,
        'delivery_dates': [day for day in working if day > futures_last][:2],
        'margin_20pct_start_date': stage_20pct,
    }

    snapshots = {}
    for row in read_csv(Path(calendar['_input_dir']) / 'futures_snapshots.csv'):
        date = row['snapshot_date']
        stage = int(date >= prior_days[0]) + int(date >= delivery_days[0])
        rate = rates[3] if date >= stage_20pct else rates[stage]
        offset = 1 if row['participant_type'] == 'customer' else 0
        limit = int(limits[stage * 2 + offset])
        long_lots, short_lots = int(row['long_lots']), int(row['short_lots'])
        price = Decimal(row['settlement_cny_per_kg'])
        previous = Decimal(row['previous_settlement_cny_per_kg'])
        equity_before = Decimal(row['equity_before_vm_cny'])
        vm = (long_lots - short_lots) * (price - previous) * multiplier
        equity = equity_before + vm
        margin = (long_lots + short_lots) * price * multiplier * rate
        parity_required = date >= prior_days[-1]
        snapshots[row['row_id']] = {
            'margin_rate': rate, 'directional_limit_lots': limit,
            'long_lots': long_lots, 'short_lots': short_lots,
            'long_excess_lots': max(long_lots - limit, 0),
            'short_excess_lots': max(short_lots - limit, 0),
            'parity_required': parity_required,
            'parity_compliant': (not parity_required) or (long_lots % 2 == 0 and short_lots % 2 == 0),
            'variation_margin_cny': vm, 'equity_after_vm_cny': equity,
            'required_margin_cny': margin, 'additional_funds_cny': max(margin - equity, Decimal(0)),
            'settlement': price,
        }

    events = {}
    for event in read_csv(Path(calendar['_input_dir']) / 'option_requests.csv'):
        moment = event['request_at']
        date, clock = moment[:10], moment[11:19]
        quantity, available = int(event['quantity_lots']), int(event['available_lots'])
        in_session = ('09:00:00' <= clock <= '11:30:00') or ('13:30:00' <= clock <= '15:00:00')
        valid = (date in trading and date <= expiry and 0 < quantity <= available
                 and ((date == expiry and clock < '15:30:00') or (date < expiry and in_session)))
        disposition = event['request'] if valid else 'reject'
        long_lots = quantity if disposition == 'exercise' and event['option_type'] == 'call' else 0
        short_lots = quantity if disposition == 'exercise' and event['option_type'] == 'put' else 0
        base = snapshots[event['base_row_id']]
        vm = (long_lots - short_lots) * (base['settlement'] - Decimal(event['strike_cny_per_kg'])) * multiplier
        events[event['event_id']] = {
            'time_and_inventory_valid': valid, 'request_disposition': disposition,
            'added_long_lots': long_lots, 'added_short_lots': short_lots,
            'incremental_vm_cny': vm, 'base_row_id': event['base_row_id'],
        }

    post = {}
    for base_id in ['R03', 'R11']:
        base = snapshots[base_id]
        applied = [eid for eid, e in events.items()
                   if e['base_row_id'] == base_id and e['request_disposition'] == 'exercise']
        long_lots = base['long_lots'] + sum(events[e]['added_long_lots'] for e in applied)
        short_lots = base['short_lots'] + sum(events[e]['added_short_lots'] for e in applied)
        incremental = sum((events[e]['incremental_vm_cny'] for e in applied), Decimal(0))
        equity = base['equity_after_vm_cny'] + incremental
        margin = (long_lots + short_lots) * base['settlement'] * multiplier * base['margin_rate']
        post[base_id] = {
            'applied_event_ids': sorted(applied), 'long_lots': long_lots, 'short_lots': short_lots,
            'long_excess_lots': max(long_lots - base['directional_limit_lots'], 0),
            'short_excess_lots': max(short_lots - base['directional_limit_lots'], 0),
            'incremental_vm_cny': incremental, 'equity_after_vm_cny': equity,
            'required_margin_cny': margin, 'additional_funds_cny': max(margin - equity, Decimal(0)),
        }

    plans = {}
    for plan in read_csv(Path(calendar['_input_dir']) / 'proposed_trade_plans.csv'):
        base = snapshots[plan['base_row_id']]
        acts = [int(plan[k]) for k in
                ['open_long_lots', 'open_short_lots', 'close_long_lots', 'close_short_lots']]
        in_delivery_month = plan['submitted_at'][:7] == '2026-12'
        long_lots = base['long_lots'] + acts[0] - acts[2]
        short_lots = base['short_lots'] + acts[1] - acts[3]
        plans[plan['plan_id']] = {
            'transaction_lot_parity_valid': (not in_delivery_month) or all(q % 2 == 0 for q in acts),
            'resulting_long_lots': long_lots, 'resulting_short_lots': short_lots,
            'resulting_long_excess_lots': max(long_lots - base['directional_limit_lots'], 0),
            'resulting_short_excess_lots': max(short_lots - base['directional_limit_lots'], 0),
            'resulting_position_parity_valid': (not base['parity_required'])
            or (long_lots % 2 == 0 and short_lots % 2 == 0),
        }

    quotes = {}
    for quote in read_csv(Path(calendar['_input_dir']) / 'proposed_option_quotes.csv'):
        premium = Decimal(quote['premium_cny_per_kg'])
        quantity = int(quote['quantity_lots'])
        lower = (premium // tick) * tick
        quotes[quote['quote_id']] = {
            'tick_valid': premium % tick == 0,
            'one_lot_tick_value_cny': tick * multiplier,
            'quoted_quantity_tick_value_cny': quantity * tick * multiplier,
            'nearest_lower_valid_quote': lower,
            'nearest_upper_valid_quote': lower if premium % tick == 0 else lower + tick,
        }

    return {'timeline': timeline, 'snapshots': snapshots, 'events': events,
            'post': post, 'plans': plans, 'quotes': quotes, 'rules': rules}


# --------------------------------------------------------------------------
# candidate reading
# --------------------------------------------------------------------------

class Candidate:
    def __init__(self, output_dir):
        self.dir = Path(output_dir)
        self.defects = []
        self.funding = {}
        self.ledger = []
        self.ledger_columns = []
        self.memo = ''
        self._load()

    def _load(self):
        funding_path = self.dir / 'funding_results.json'
        if not funding_path.is_file():
            self.defects.append('funding_results.json missing')
        else:
            try:
                self.funding = json.loads(funding_path.read_text(encoding='utf-8'))
            except (ValueError, UnicodeDecodeError) as exc:
                self.defects.append(f'funding_results.json unreadable: {exc}')
                self.funding = {}

        ledger_path = self.dir / 'risk_ledger.csv'
        if not ledger_path.is_file():
            self.defects.append('risk_ledger.csv missing')
        else:
            try:
                self.ledger = read_csv(ledger_path)
                self.ledger_columns = list(self.ledger[0].keys()) if self.ledger else []
            except Exception as exc:
                self.defects.append(f'risk_ledger.csv unreadable: {exc}')

        memo_path = self.dir / 'action_memo.md'
        if not memo_path.is_file():
            self.defects.append('action_memo.md missing')
        else:
            try:
                self.memo = memo_path.read_text(encoding='utf-8')
            except (OSError, UnicodeDecodeError) as exc:
                self.defects.append(f'action_memo.md unreadable: {exc}')

    def rows(self, key, ident):
        """Index a top-level list by its identifier field."""
        rows = self.funding.get(key)
        if not isinstance(rows, list):
            return {}
        index = {}
        for row in rows:
            if isinstance(row, dict) and isinstance(row.get(ident), str):
                index.setdefault(row[ident], row)
        return index


def close(got, want, tol=TOL):
    if isinstance(want, bool) or isinstance(got, bool):
        return got is want
    if isinstance(want, (int, Decimal, float)) and not isinstance(want, str):
        try:
            return abs(Decimal(str(got)) - Decimal(str(want))) <= tol
        except Exception:
            return False
    return got == want


def close_timestamp(got, want):
    """Accept equivalent instants written in another timezone or format."""
    try:
        a = datetime.fromisoformat(str(got))
        b = datetime.fromisoformat(str(want))
    except Exception:
        return got == want
    if a.tzinfo is None or b.tzinfo is None:
        return str(got) == str(want)
    return a.astimezone(timezone.utc) == b.astimezone(timezone.utc)


# --------------------------------------------------------------------------
# assertions
# --------------------------------------------------------------------------

def evaluate(cand, exp, calendar):
    """Return [(assertion_id, passed, detail)]. Each entry is one work unit."""
    out = []

    def add(aid, passed, detail):
        out.append((aid, bool(passed), detail))

    # ---- R1 -----------------------------------------------------------------
    # One work unit per baseline: a row is either reconciled or it is not.
    # Bucketing all 11 rows into one assertion would let a single wrong row
    # cost only 1/N of the score, which is exactly the saturation we are
    # trying to avoid. The per-row fields are one口径, so they stay together.
    got = cand.rows('futures_snapshots', 'row_id')
    fields = ['margin_rate', 'variation_margin_cny', 'equity_after_vm_cny',
              'required_margin_cny', 'additional_funds_cny']
    tolerances = {'margin_rate': Decimal('1e-9')}
    for row_id, want in exp['snapshots'].items():
        have = got.get(row_id, {})
        if not have:
            add(f'R1.{row_id}', False, f'{row_id} 缺失')
            continue
        bad = [k for k in fields
               if not close(have.get(k), want[k], tolerances.get(k, TOL))]
        add(f'R1.{row_id}', not bad,
            f'{row_id} 费率={have.get("margin_rate")} VM={have.get("variation_margin_cny")} '
            f'权益={have.get("equity_after_vm_cny")} 保证金={have.get("required_margin_cny")} '
            f'追加={have.get("additional_funds_cny")}'
            + (f' | 不符字段 {bad}' if bad else ''))

    # The multiplier is only observable through magnitudes, so anchor it on a
    # row where gross and net positions differ and the rate is not the outlier.
    probe = exp['snapshots']['R02']
    probe_have = got.get('R02', {})
    probe_ok = (close(probe_have.get('margin_rate'), probe['margin_rate'], Decimal('1e-9'))
                and close(probe_have.get('variation_margin_cny'), probe['variation_margin_cny'])
                and close(probe_have.get('required_margin_cny'), probe['required_margin_cny']))
    add('R1.contract-params', probe_ok,
        '乘数15千克/手已由R02量级验证' if probe_ok else 'R02量级不符，乘数或单位错误')

    # Understating a funding gap is materially different from miscomputing one
    # figure: the desk acts on this number, so writing 0 where the recomputation
    # is positive is its own work unit with its own cap.
    understated = []
    for row_id, want in exp['snapshots'].items():
        if want['additional_funds_cny'] <= 0:
            continue
        have = got.get(row_id, {}).get('additional_funds_cny')
        try:
            if Decimal(str(have)) <= 0:
                understated.append(row_id)
        except Exception:
            understated.append(row_id)
    add('R1.funding-understatement', not understated,
        '全部非零资金缺口均已如实报告' if not understated
        else f'资金缺口被实质性低报: {understated}')

    # ---- R2 -----------------------------------------------------------------
    lim_bad = [r for r, e in exp['snapshots'].items()
               if not close(got.get(r, {}).get('directional_limit_lots'), e['directional_limit_lots'])]
    add('R2.directional-limits', not lim_bad,
        '限仓档位全部正确' if not lim_bad else f'限仓不符: {lim_bad}')

    exc_bad = [r for r, e in exp['snapshots'].items()
               if not (close(got.get(r, {}).get('long_excess_lots'), e['long_excess_lots'])
                       and close(got.get(r, {}).get('short_excess_lots'), e['short_excess_lots']))]
    add('R2.excess-per-direction', not exc_bad,
        '逐方向超限全部正确' if not exc_bad else f'超限不符: {exc_bad}')

    par_req_bad = [r for r, e in exp['snapshots'].items()
                   if not close(got.get(r, {}).get('parity_required'), e['parity_required'])]
    add('R2.parity-rule', not par_req_bad,
        '2手整数倍适用时点全部正确' if not par_req_bad else f'适用时点不符: {par_req_bad}')

    par_cmp_bad = [r for r, e in exp['snapshots'].items()
                   if not close(got.get(r, {}).get('parity_compliant'), e['parity_compliant'])]
    add('R2.parity-compliance', not par_cmp_bad,
        '持仓数量合规判定全部正确' if not par_cmp_bad else f'合规判定不符: {par_cmp_bad}')

    # ---- R3 -----------------------------------------------------------------
    timeline = cand.funding.get('contract_timeline') or {}
    if not isinstance(timeline, dict):
        timeline = {}

    def date_check(aid, field, allow_utc=False):
        want = exp['timeline'][field]
        have = timeline.get(field)
        ok = close_timestamp(have, want) if allow_utc else have == want
        add(aid, ok, f'{field}={have!r} (期望 {want!r})')

    date_check('R3.option-expiry', 'option_expiry_date')
    date_check('R3.exercise-cutoff', 'option_expiry_exercise_cutoff', allow_utc=True)
    date_check('R3.futures-last', 'futures_last_trading_date')
    got_delivery = timeline.get('delivery_dates')
    add('R3.delivery-days', isinstance(got_delivery, list)
        and [str(x) for x in got_delivery] == exp['timeline']['delivery_dates'],
        f'delivery_dates={got_delivery!r}')
    date_check('R3.margin-stage-start', 'margin_20pct_start_date')

    # ---- R4 -----------------------------------------------------------------
    events = cand.rows('option_requests', 'event_id')
    valid_bad = [e for e, want in exp['events'].items()
                 if not close(events.get(e, {}).get('time_and_inventory_valid'),
                              want['time_and_inventory_valid'])]
    add('R4.admissibility', not valid_bad,
        '请求有效性与持有数量判定全部正确' if not valid_bad else f'有效性不符: {valid_bad}')

    disp_bad = [e for e, want in exp['events'].items()
                if events.get(e, {}).get('request_disposition') != want['request_disposition']]
    add('R4.disposition', not disp_bad,
        '处置结论全部正确' if not disp_bad else f'处置不符: {disp_bad}')

    direction_bad = [e for e, want in exp['events'].items()
                     if not (close(events.get(e, {}).get('added_long_lots'), want['added_long_lots'])
                             and close(events.get(e, {}).get('added_short_lots'), want['added_short_lots']))]
    add('R4.call-put-direction', not direction_bad,
        '看涨加多/看跌加空映射正确' if not direction_bad else f'方向映射不符: {direction_bad}')

    vm_bad = [e for e, want in exp['events'].items()
              if not close(events.get(e, {}).get('incremental_vm_cny'), want['incremental_vm_cny'])]
    add('R4.incremental-vm', not vm_bad,
        '增量VM全部正确' if not vm_bad else f'增量VM不符: {vm_bad}')

    post = cand.rows('post_option_snapshots', 'base_row_id')

    def post_pos(aid, base_id):
        want, have = exp['post'][base_id], post.get(base_id, {})
        ok = all(close(have.get(k), want[k]) for k in
                 ['long_lots', 'short_lots', 'long_excess_lots', 'short_excess_lots'])
        add(aid, ok,
            f'{base_id} 多{have.get("long_lots")}/空{have.get("short_lots")} '
            f'超限{have.get("long_excess_lots")}/{have.get("short_excess_lots")}')

    def post_fund(aid, base_id):
        want, have = exp['post'][base_id], post.get(base_id, {})
        ok = all(close(have.get(k), want[k]) for k in
                 ['incremental_vm_cny', 'equity_after_vm_cny',
                  'required_margin_cny', 'additional_funds_cny'])
        add(aid, ok, f'{base_id} 保证金={have.get("required_margin_cny")} '
                     f'追加={have.get("additional_funds_cny")}')

    post_pos('R4.R03-post-position', 'R03')
    post_fund('R4.R03-post-funding', 'R03')
    post_pos('R4.R11-post-position', 'R11')
    post_fund('R4.R11-post-funding', 'R11')

    # Which events were stacked onto which baseline is its own decision: a
    # candidate can get every number right by applying the wrong event set.
    applied_detail, applied_ok = [], True
    for base_id, want in exp['post'].items():
        applied = (post.get(base_id) or {}).get('applied_event_ids')
        if not isinstance(applied, list):
            applied_ok = False
            applied_detail.append(f'{base_id} applied_event_ids 缺失或非数组')
            continue
        expected_set = set(want['applied_event_ids'])
        if not expected_set <= set(applied):
            applied_ok = False
            applied_detail.append(f'{base_id} 缺少有效行权 {sorted(expected_set - set(applied))}')
        # Rejected requests must never be applied; a zero-effect abandonment may.
        rejected = {eid for eid, e in exp['events'].items()
                    if e['request_disposition'] == 'reject'}
        if rejected & set(applied):
            applied_ok = False
            applied_detail.append(f'{base_id} 误用被拒事件 {sorted(rejected & set(applied))}')
    add('R4.applied-events', applied_ok,
        '；'.join(applied_detail) if applied_detail else '叠加压力所应用的事件集合正确')

    # ---- R5 -----------------------------------------------------------------
    plans = cand.rows('trade_plan_checks', 'plan_id')

    def plan_check(aid, plan_id, fields):
        want, have = exp['plans'][plan_id], plans.get(plan_id, {})
        bad = [k for k in fields if not close(have.get(k), want[k])]
        detail = ', '.join(f'{k}={have.get(k)}' for k in fields)
        add(aid, not bad, f'{plan_id}: {detail}' + (f' | 不符字段 {bad}' if bad else ''))

    plan_check('R5.tp01', 'TP01',
               ['transaction_lot_parity_valid', 'resulting_long_lots', 'resulting_short_lots',
                'resulting_long_excess_lots', 'resulting_position_parity_valid'])
    plan_check('R5.tp02', 'TP02',
               ['transaction_lot_parity_valid', 'resulting_long_lots', 'resulting_short_lots',
                'resulting_long_excess_lots', 'resulting_short_excess_lots',
                'resulting_position_parity_valid'])
    plan_check('R5.tp03', 'TP03',
               ['transaction_lot_parity_valid', 'resulting_long_lots', 'resulting_short_lots',
                'resulting_position_parity_valid'])
    plan_check('R5.tp04', 'TP04',
               ['transaction_lot_parity_valid', 'resulting_long_lots', 'resulting_short_lots',
                'resulting_long_excess_lots', 'resulting_short_excess_lots',
                'resulting_position_parity_valid'])

    # Disposition is a closed vocabulary declared in output_schema.md, so it is
    # objectively checkable. The professional *reasoning* stays in `reason` and
    # is not scored here -- only the conclusion is, and only where the trading
    # rule admits one answer.
    disposition_rules = {
        # 交割月新开1手违反2手倍数，且结果901为奇数 -> 不可执行
        'TP01': ('reject',),
        # 平空2手合法减仓，仍须落实资金控制 -> 可执行但附条件（暂缓核查亦可）
        'TP02': ('approve_with_controls', 'review'),
        # 交割月平1手违反2手倍数，不能借此修复既有奇数异常 -> 不可执行
        'TP03': ('reject',),
        # 前月末各平1手同时修复超限与奇偶 -> 可执行但附条件
        'TP04': ('approve_with_controls', 'review'),
    }
    for plan_id, allowed in disposition_rules.items():
        have = (plans.get(plan_id) or {}).get('disposition')
        add(f'R5.{plan_id.lower()}-disposition', have in allowed,
            f'{plan_id} 处置={have!r}（允许 {allowed}）')

    # ---- R6 -----------------------------------------------------------------
    quotes = cand.rows('quote_checks', 'quote_id')
    for quote_id, want in exp['quotes'].items():
        have = quotes.get(quote_id, {})
        grid_bad = [k for k in ['tick_valid', 'nearest_lower_valid_quote', 'nearest_upper_valid_quote']
                    if not close(have.get(k), want[k])]
        add('R6.tick-grid', not grid_bad,
            f'{quote_id} 网格={have.get("tick_valid")} '
            f'相邻={have.get("nearest_lower_valid_quote")}/{have.get("nearest_upper_valid_quote")}')
        value_bad = [k for k in ['one_lot_tick_value_cny', 'quoted_quantity_tick_value_cny']
                     if not close(have.get(k), want[k])]
        add('R6.tick-value', not value_bad,
            f'{quote_id} 单手={have.get("one_lot_tick_value_cny")} '
            f'所报数量={have.get("quoted_quantity_tick_value_cny")}')

    # ---- R7 -----------------------------------------------------------------
    required = {'object_id', 'object_type', 'assessment', 'severity',
                'rule_locator', 'corrective_action', 'due_at'}
    columns_ok = bool(cand.ledger) and not (required - set(cand.ledger_columns))
    add('R7.ledger-columns', columns_ok,
        f'必有列={sorted(required & set(cand.ledger_columns))}'
        + (f' | 缺少 {sorted(required - set(cand.ledger_columns))}'
           if required - set(cand.ledger_columns) else ''))

    object_ids = ({f'R{i:02d}' for i in range(1, 12)}
                  | set(exp['events']) | set(exp['plans']) | set(exp['quotes']))
    covered = {row.get('object_id') for row in cand.ledger}
    missing = sorted(object_ids - covered)
    add('R7.ledger-object-coverage', bool(cand.ledger) and not missing,
        f'覆盖 {len(object_ids - set(missing))}/{len(object_ids)} 个对象'
        + (f' | 缺 {missing[:8]}' if missing else ''))

    # A bare pass/fail label is not a professional assessment; a finding needs
    # the quantified difference it rests on.
    vague = [row.get('object_id') for row in cand.ledger
             if not re.search(r'\d', row.get('assessment') or '')]
    add('R7.ledger-quantified', bool(cand.ledger) and len(vague) <= 2,
        '全部assessment含量化差额' if not vague else f'缺少量化差额: {vague[:6]}')

    memo = cand.memo
    expiry, futures_last = (exp['timeline']['option_expiry_date'],
                            exp['timeline']['futures_last_trading_date'])
    delivery = exp['timeline']['delivery_dates']
    stage_start = exp['timeline']['margin_20pct_start_date']
    # Dates may be written as ISO strings or in ordinary Chinese business style,
    # and consecutive days are commonly run together ("12月16、17日"). All of
    # these are legitimate encodings, so expand them before comparing -- a
    # correct memo must never be penalized for wording.
    def expand_dates(text):
        found = set(re.findall(r'\d{4}-\d{2}-\d{2}', text))
        for month, rest in re.findall(r'(\d{1,2})月([0-9、,，\s]+)日', text):
            for day in re.findall(r'\d{1,2}', rest):
                found.add(f'2026-{int(month):02d}-{int(day):02d}')
        return found

    memo_dates = expand_dates(memo)
    required_dates = {expiry, futures_last, stage_start, *delivery}
    missing_dates = sorted(required_dates - memo_dates)
    add('R7.memo-coverage',
        len(memo.strip()) >= 80 and not missing_dates,
        f'长度={len(memo.strip())} 覆盖期限 {len(required_dates) - len(missing_dates)}/{len(required_dates)}'
        + (f' | 缺少 {missing_dates}' if missing_dates else ''))

    # Layering is checked structurally, not by keyword: the memo must cite the
    # attached originals for its rule conclusions AND declare the internal
    # operational arrangement that does not change the exchange timetable.
    cites_sources = sum(1 for token in ('F047', 'F042') if token in memo)
    declares_internal = ('暂停' in memo or '值守' in memo)
    add('R7.memo-layering', cites_sources == 2 and declares_internal,
        f'引用原件 {cites_sources}/2 项，声明内部运营安排={declares_internal}')

    # ---- R3 期限区分（依据断言）---------------------------------------------
    # The three counting rules use different bases; conflating them is the
    # classic calendar error, so it is the timeout/notice distinction itself
    # that is checked, not another copy of the dates.
    stage_start = exp['timeline']['margin_20pct_start_date']
    trading = calendar['trading']
    idx = trading.index(futures_last)
    delivery_ok = stage_start == trading[idx - 2] and stage_start < futures_last
    add('R3.deadline-distinction', delivery_ok,
        f'20%阶段起点按期货最后交易日倒数第二个交易日推出={stage_start}')

    return out


# --------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------

def write_report(log_dir, payload):
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / 'report.json').write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--log-dir', type=Path, default=Path('/logs/verifier'))
    parser.add_argument('--tests-dir', type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()

    log_dir, tests_dir = args.log_dir, args.tests_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    # A stale reward must never mask this run's outcome. Only the JSON reward is
    # part of the delivery contract, so that is the only thing written here.
    (log_dir / 'reward.json').unlink(missing_ok=True)

    contract = json.loads((tests_dir / 'assertions.json').read_text(encoding='utf-8'))
    declarations = contract['assertions']
    scale = Decimal(str(contract['scale']))

    input_dir = tests_dir / 'input-data'
    try:
        rules = read_rules(input_dir)
        calendar = read_calendar(input_dir)
        calendar['_input_dir'] = input_dir
        exp = derive_expectations(rules, calendar)
    except Exception as exc:
        # Trusted-input or scoring-dependency fault: no reward at all.
        write_report(log_dir, {
            'task_id': TASK_ID, 'status': 'verifier_failure', 'valid': False,
            'verifier_failed': True, 'error_type': type(exc).__name__, 'error': str(exc),
            'reward_emitted': False,
        })
        print(json.dumps({'status': 'verifier_failure', 'error': str(exc)}, ensure_ascii=False))
        return 1

    candidate = Candidate(args.output_dir)
    results = evaluate(candidate, exp, calendar)
    by_id = {aid: (passed, detail) for aid, passed, detail in results}

    assertions = []
    for declared in declarations:
        passed, detail = by_id.get(declared['id'], (False, '断言未产生结果'))
        assertions.append({**declared, 'status': 'passed' if passed else 'failed', 'detail': detail})

    passed_count = sum(1 for a in assertions if a['status'] == 'passed')
    proportional = Decimal(passed_count) / scale
    proportional = min(proportional, Decimal(1))

    # Critical-error caps only ever lower the score.
    caps = []
    for critical in contract.get('critical_errors') or []:
        target = next((a for a in assertions if a['id'] == critical['assertion']), None)
        if target is not None and target['status'] == 'failed':
            caps.append({'id': critical['id'], 'assertion': critical['assertion'],
                         'cap': critical['cap'], 'reason': target['detail']})
    ceiling = Decimal(str(min([c['cap'] for c in caps], default=1.0)))
    reward = min(proportional, ceiling)

    status = 'graded_candidate_defect' if candidate.defects else 'graded'
    payload = {
        'task_id': TASK_ID,
        'status': status,
        'valid': True,
        'verifier_failed': False,
        'reward_emitted': True,
        'scale': int(scale),
        'passed': passed_count,
        'reward': float(reward),
        'reward_before_caps': float(proportional),
        'critical_error_caps': caps,
        'candidate_defects': candidate.defects,
        'criteria': sorted({a['criterion'] for a in assertions}),
        'assertions': assertions,
        'aggregation': 'reward = P / S, P 为通过断言绝对数，S 为断言总数；critical error 只降低分数。',
    }
    write_report(log_dir, payload)
    (log_dir / 'reward.json').write_text(
        json.dumps({'reward': float(reward), 'status': status,
                    'passed': passed_count, 'scale': int(scale)}, ensure_ascii=False) + '\n',
        encoding='utf-8')

    print(json.dumps({'status': status, 'passed': passed_count, 'scale': int(scale),
                      'reward': float(reward), 'caps': caps,
                      'failed': [a['id'] for a in assertions if a['status'] == 'failed']},
                     ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
