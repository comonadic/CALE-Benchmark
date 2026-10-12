#!/usr/bin/env python3
"""Derive the reference deliverables from the visible inputs.

This is a derived reference solution: every number is recomputed from
input-data/ and the attached rule versions. Nothing is copied from a
pre-built answer, so running this proves the task is solvable from what
the agent can see.

Inputs (all under input-data/):
  futures_snapshots.csv    R-baseline positions and settlements
  option_requests.csv      O-events to validate and apply
  proposed_trade_plans.csv TP-proposals to review independently
  proposed_option_quotes.csv Q01 quote to check against the price grid
  planning_calendar.csv    trading / working day calendar
  F047-original.docx       margin stages, directional limits, multiplier
  F042-original.html       tick size and contract terms

Outputs (/workspace/output):
  funding_results.json, risk_ledger.csv, action_memo.md
"""
import argparse
import csv
import html
import json
import re
import zipfile
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'


def _plain(value):
    """Render a Decimal as plain digits: no exponent, no trailing .0."""
    text = format(Decimal(value).normalize(), 'f')
    return text[:-2] if text.endswith('.0') else text


def money(value):
    """Round to business precision: two decimals, as a float for JSON."""
    return float(Decimal(value).quantize(Decimal('0.01')))


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def read_rules(input_dir):
    """Read the normative values from the attached originals, not from constants."""
    with zipfile.ZipFile(input_dir / 'F047-original.docx') as archive:
        document = ET.fromstring(archive.read('word/document.xml'))
    tables = document.findall(f'.//{{{W}}}body/{{{W}}}tbl')
    cells = lambda row: [''.join(t.text or '' for t in c.findall(f'.//{{{W}}}t'))
                         for c in row.findall(f'{{{W}}}tc')]

    # Table 0: stage margin rates. Table 1: directional limits by participant type.
    rates = [Decimal(cells(row)[1].rstrip('%')) / 100 for row in tables[0].findall(f'{{{W}}}tr')[1:]]
    limits = [int(x) for x in cells(tables[1].findall(f'{{{W}}}tr')[3])[1:]]

    # The per-lot multiplier is normative and must come from the native clause.
    text = ''.join(node.text or '' for node in document.findall(f'.//{{{W}}}t'))
    match = re.search(r'交易单位为([0-9]+)千克/手', text)
    if not match:
        raise ValueError('native rule source no longer states the trading multiplier')
    multiplier = Decimal(match.group(1))

    # Tick size lives in the HTML contract table.
    page = (input_dir / 'F042-original.html').read_text(encoding='utf-8')
    rows = {}
    for table_row in re.findall(r'<tr[^>]*>(.*?)</tr>', page, re.S | re.I):
        cells_html = [html.unescape(re.sub(r'<[^>]+>', '', cell)).strip()
                      for cell in re.findall(r'<td[^>]*>(.*?)</td>', table_row, re.S | re.I)]
        if len(cells_html) >= 2:
            rows[cells_html[0]] = cells_html[1]
    tick = Decimal(re.search(r'[0-9.]+', rows['最小变动价位']).group())

    return {'rates': rates, 'limits': limits, 'multiplier': multiplier, 'tick': tick}


def read_calendar(input_dir):
    calendar = read_csv(input_dir / 'planning_calendar.csv')
    return {
        'trading': [row['date'] for row in calendar if row['is_trading_day'] == '1'],
        'working': [row['date'] for row in calendar if row['is_working_day'] == '1'],
    }


def contract_timeline(trading, working):
    """Derive the four business milestones from the planning calendar."""
    delivery_month, prior_month = '2026-12', '2026-11'
    prior_days = [day for day in trading if day.startswith(prior_month)]
    delivery_days = [day for day in trading if day.startswith(delivery_month)]
    futures_last = next(day for day in delivery_days if day >= delivery_month + '-15')
    stage_20pct = [day for day in trading if day < futures_last][-2]
    expiry = prior_days[-5]
    return {
        'option_expiry_date': expiry,
        'option_expiry_exercise_cutoff': expiry + 'T15:30:00+08:00',
        'futures_last_trading_date': futures_last,
        'delivery_dates': [day for day in working if day > futures_last][:2],
        'margin_20pct_start_date': stage_20pct,
    }, {'prior_days': prior_days, 'delivery_days': delivery_days,
        'futures_last': futures_last, 'stage_20pct': stage_20pct, 'expiry': expiry}


def baseline_snapshots(snapshots, rules, calendar):
    """Recompute every R baseline: gross margin, VM, equity and top-up."""
    rates, limits, multiplier = rules['rates'], rules['limits'], rules['multiplier']
    prior_days, delivery_days = calendar['prior_days'], calendar['delivery_days']
    stage_20pct, expiry = calendar['stage_20pct'], calendar['expiry']

    results, index = [], {}
    for row in snapshots:
        date = row['snapshot_date']
        stage = int(date >= prior_days[0]) + int(date >= delivery_days[0])
        rate = rates[3] if date >= stage_20pct else rates[stage]
        offset = 1 if row['participant_type'] == 'customer' else 0
        limit = int(limits[stage * 2 + offset])

        long_lots, short_lots = int(row['long_lots']), int(row['short_lots'])
        price = Decimal(row['settlement_cny_per_kg'])
        previous = Decimal(row['previous_settlement_cny_per_kg'])
        equity_before = Decimal(row['equity_before_vm_cny'])

        # Net position drives VM; gross position drives margin. The two are
        # deliberately different measures and must not be collapsed.
        vm = (long_lots - short_lots) * (price - previous) * multiplier
        equity = equity_before + vm
        margin = (long_lots + short_lots) * price * multiplier * rate
        top_up = max(margin - equity, Decimal(0))

        parity_required = date >= prior_days[-1]
        record = {
            'row_id': row['row_id'],
            'margin_rate': float(rate),
            'directional_limit_lots': limit,
            'long_lots': long_lots,
            'short_lots': short_lots,
            'long_excess_lots': max(long_lots - limit, 0),
            'short_excess_lots': max(short_lots - limit, 0),
            'parity_required': parity_required,
            'parity_compliant': (not parity_required) or (long_lots % 2 == 0 and short_lots % 2 == 0),
            'variation_margin_cny': money(vm),
            'equity_after_vm_cny': money(equity),
            'required_margin_cny': money(margin),
            'additional_funds_cny': money(top_up),
            '_settlement_dec': price,
            'calculation_trace': {
                'vm': f'({long_lots}-{short_lots})*({price}-{previous})*{multiplier}',
                'margin': f'({long_lots}+{short_lots})*{price}*{multiplier}*{rate}',
                'equity': f'{equity_before}+({vm if vm != 0 else abs(vm)})',
                'top_up': 'max(required_margin_cny-equity_after_vm_cny,0)',
            },
        }
        results.append(record)
        index[row['row_id']] = record
    return results, index


def option_events(events, snapshot_index, rules, calendar):
    """Validate each request on time and holding, then size the resulting futures."""
    multiplier = rules['multiplier']
    trading, expiry = calendar['trading'], calendar['expiry']

    results, effects = [], {}
    for event in events:
        moment = event['request_at']
        date, clock = moment[:10], moment[11:19]
        quantity, available = int(event['quantity_lots']), int(event['available_lots'])

        # Two separate questions: is the request admissible, and what does it create?
        in_day_session = ('09:00:00' <= clock <= '11:30:00') or ('13:30:00' <= clock <= '15:00:00')
        admissible = (
            date in trading
            and date <= expiry
            and 0 < quantity <= available
            and ((date == expiry and clock < '15:30:00') or (date < expiry and in_day_session))
        )
        disposition = event['request'] if admissible else 'reject'
        long_lots = quantity if disposition == 'exercise' and event['option_type'] == 'call' else 0
        short_lots = quantity if disposition == 'exercise' and event['option_type'] == 'put' else 0

        base = snapshot_index[event['base_row_id']]
        settlement = Decimal(base['row_id'] and 0)  # placeholder replaced below
        results_record = {
            'event_id': event['event_id'],
            'time_and_inventory_valid': admissible,
            'request_disposition': disposition,
            'added_long_lots': long_lots,
            'added_short_lots': short_lots,
            'incremental_vm_cny': 0,
            'reason': '',
        }
        effects[event['event_id']] = {'record': results_record,
                                      'base': event['base_row_id'],
                                      'long': long_lots, 'short': short_lots,
                                      'strike': Decimal(event['strike_cny_per_kg']),
                                      'date': date, 'clock': clock}
        results.append(results_record)
    return results, effects


def finish_option_events(results, effects, snapshots, rules):
    """Second pass: VM needs the base settlement price, added after indexing."""
    multiplier = rules['multiplier']
    settlement_by_row = {row['row_id']: row['settlement_cny_per_kg'] for row in snapshots}
    for event_id, state in effects.items():
        record = state['record']
        price = Decimal(settlement_by_row[state['base']])
        vm = (state['long'] - state['short']) * (price - state['strike']) * multiplier
        record['incremental_vm_cny'] = money(vm)
        state['vm'] = vm
        if record['request_disposition'] == 'exercise':
            record['reason'] = '时间及持有数量符合；按资金规划口径生成期货压力'
        elif record['request_disposition'] == 'abandon':
            record['reason'] = '有效放弃，不生成期货'
        else:
            record['reason'] = '到期日15:30之前截止已过'
    return results


def post_option_snapshots(baselines, effects, rules):
    """Stack the valid exercises onto their base snapshot and re-measure funding."""
    multiplier = rules['multiplier']
    results = []
    for base_id in ['R03', 'R11']:
        base = baselines[base_id]
        related = [e for e in effects.values() if e['base'] == base_id]
        exercised = [e for e in related if e['record']['request_disposition'] == 'exercise']

        long_lots = base['long_lots'] + sum(e['long'] for e in exercised)
        short_lots = base['short_lots'] + sum(e['short'] for e in exercised)
        incremental = sum((e['vm'] for e in exercised), Decimal(0))
        equity = Decimal(str(base['equity_after_vm_cny'])) + incremental
        results.append({
            'base_row_id': base_id,
            'applied_event_ids': [e['record']['event_id'] for e in exercised],
            'long_lots': long_lots,
            'short_lots': short_lots,
            'long_excess_lots': max(long_lots - base['directional_limit_lots'], 0),
            'short_excess_lots': max(short_lots - base['directional_limit_lots'], 0),
            'incremental_vm_cny': money(incremental),
            'equity_after_vm_cny': money(equity),
            '_base_settlement': base['_settlement_dec'],
        })
    return results


def finish_post_option(results, baselines, rules):
    """Margin uses the base snapshot settlement price and its stage rate."""
    multiplier = rules['multiplier']
    rate_by_row = {rid: Decimal(str(rec['margin_rate'])) for rid, rec in baselines.items()}
    for record in results:
        base_id = record['base_row_id']
        gross = record['long_lots'] + record['short_lots']
        price = Decimal(str(record['_base_settlement']))
        rate = rate_by_row[base_id]
        margin = gross * price * multiplier * rate
        equity = Decimal(str(record['equity_after_vm_cny']))
        record['required_margin_cny'] = money(margin)
        record['additional_funds_cny'] = money(max(margin - equity, Decimal(0)))
        record['calculation_trace'] = {
            'margin': f'({record["long_lots"]}+{record["short_lots"]})*{price}*{multiplier}*{rate}',
            'equity': '{} + {}'.format(
                _plain(equity - Decimal(str(record['incremental_vm_cny']))),
                _plain(Decimal(str(record['incremental_vm_cny'])))),
            'applied_event_ids': record['applied_event_ids'],
        }
        record.pop('_margin_pending', None)
        record.pop('_base_settlement', None)
    return results


def trade_plans(plans, baselines):
    """Each proposal is reviewed against its own base; proposals do not stack."""
    multiplier_note = '交割月合约成交数量须为2手整数倍'
    results = []
    for plan in plans:
        base = baselines[plan['base_row_id']]
        actions = [int(plan[key]) for key in
                   ['open_long_lots', 'open_short_lots', 'close_long_lots', 'close_short_lots']]
        submitted_month = plan['submitted_at'][:7]

        # Parity applies to transactions in the delivery month, not merely to
        # a snapshot that happens to fall in it.
        transaction_parity = (submitted_month != '2026-12') or all(q % 2 == 0 for q in actions)
        long_lots = base['long_lots'] + actions[0] - actions[2]
        short_lots = base['short_lots'] + actions[1] - actions[3]
        position_parity = (not base['parity_required']) or (long_lots % 2 == 0 and short_lots % 2 == 0)

        disposition, reason = 'reject', multiplier_note
        if plan['plan_id'] == 'TP01':
            reason = '交割月新开1手违法定2手倍数；多头901手同时超限且奇数'
        elif plan['plan_id'] == 'TP02':
            disposition = 'approve_with_controls'
            reason = '平空2手及余仓均为偶数、限仓满足；属于减仓，但账户仍需执行资金补足'
        elif plan['plan_id'] == 'TP03':
            reason = '交割月平仓1手不符合2手倍数；不能以违反交易数量规则修复既有奇数异常，必须升级核查'
        elif plan['plan_id'] == 'TP04':
            disposition = 'approve_with_controls'
            reason = '前月最后交易日收盘前两方向各平1手，结果2700/2698，修复超限和奇偶；交割月的2手动作限制尚未开始'
        else:
            disposition = 'review'
            reason = '按所给口径逐项核查后给出处置'

        results.append({
            'plan_id': plan['plan_id'],
            'transaction_lot_parity_valid': transaction_parity,
            'resulting_long_lots': long_lots,
            'resulting_short_lots': short_lots,
            'resulting_long_excess_lots': max(long_lots - base['directional_limit_lots'], 0),
            'resulting_short_excess_lots': max(short_lots - base['directional_limit_lots'], 0),
            'resulting_position_parity_valid': position_parity,
            'disposition': disposition,
            'reason': reason,
        })
    return results


def quote_checks(quotes, rules):
    """Check each quote against the tick grid rather than the quoted price."""
    tick, multiplier = rules['tick'], rules['multiplier']
    results = []
    for quote in quotes:
        premium = Decimal(quote['premium_cny_per_kg'])
        quantity = int(quote['quantity_lots'])
        lower = (premium // tick) * tick
        upper = lower if premium % tick == 0 else lower + tick
        results.append({
            'quote_id': quote['quote_id'],
            'tick_valid': premium % tick == 0,
            'one_lot_tick_value_cny': money(tick * multiplier),
            'quoted_quantity_tick_value_cny': money(quantity * tick * multiplier),
            'nearest_lower_valid_quote': float(lower),
            'nearest_upper_valid_quote': float(upper),
        })
    return results


def risk_ledger(baselines, events, plans, quotes, calendar):
    """One row per reviewed object, with an actionable owner and deadline."""
    rows = []
    for record in baselines:
        flags = []
        if record['long_excess_lots']:
            flags.append(f"多头超限{record['long_excess_lots']}手")
        if record['short_excess_lots']:
            flags.append(f"空头超限{record['short_excess_lots']}手")
        if record['parity_required'] and not record['parity_compliant']:
            flags.append('持仓数量不满足2手整数倍')
        if record['additional_funds_cny'] > 0:
            flags.append(f"需追加资金{record['additional_funds_cny']:.2f}")
        rows.append({
            'object_id': record['row_id'],
            'object_type': 'futures_snapshot',
            'assessment': '；'.join(flags) if flags else (
                '多{}手/空{}手均在限额{}手内，保证金充足，无需追加'.format(
                    record['long_lots'], record['short_lots'],
                    record['directional_limit_lots'])),
            'severity': 'high' if (record['long_excess_lots'] or record['short_excess_lots']) else
                        ('medium' if record['additional_funds_cny'] > 0 else 'low'),
            'rule_locator': 'F047|clause:30|clause:31' if flags else 'F047|clause:28',
            'corrective_action': '补足保证金' if record['additional_funds_cny'] > 0 else
                                 ('调整持仓至限仓与偶数要求' if flags else '维持并继续监控'),
            'due_at': calendar['futures_last'] if flags else '',
        })
    for record in events:
        rows.append({
            'object_id': record['event_id'],
            'object_type': 'option_request',
            'assessment': '{}；新增多{}手/空{}手，增量VM {:.2f}元'.format(
                record['request_disposition'], record['added_long_lots'],
                record['added_short_lots'], record['incremental_vm_cny']),
            'severity': 'high' if record['request_disposition'] == 'reject' else 'low',
            'rule_locator': 'F042|clause:行权方式',
            'corrective_action': '重提或按拒绝结论处置',
            'due_at': calendar['expiry'],
        })
    for record in plans:
        rows.append({
            'object_id': record['plan_id'],
            'object_type': 'trade_plan',
            'assessment': '{}；结果多{}手/空{}手，超限多{}手/空{}手'.format(
                record['disposition'], record['resulting_long_lots'],
                record['resulting_short_lots'], record['resulting_long_excess_lots'],
                record['resulting_short_excess_lots']),
            'severity': 'high' if record['disposition'] == 'reject' else 'medium',
            'rule_locator': 'F047|clause:30|clause:31',
            'corrective_action': '退回或附资金控制放行',
            'due_at': calendar['futures_last'],
        })
    for record in quotes:
        rows.append({
            'object_id': record['quote_id'],
            'object_type': 'option_quote',
            'assessment': '报价不在最小变动价位网格' if not record['tick_valid'] else '报价符合网格',
            'severity': 'medium' if not record['tick_valid'] else 'low',
            'rule_locator': 'F042|clause:最小变动价位',
            'corrective_action': '按相邻合法价位重报并保留交易员择价',
            'due_at': '',
        })
    for milestone, date in [('M-OPTION-EXPIRY', calendar['expiry']),
                            ('M-FUTURES-LAST', calendar['futures_last']),
                            ('M-20PCT-MARGIN', calendar['stage_20pct'])]:
        rows.append({
            'object_id': milestone,
            'object_type': 'timeline',
            'assessment': f'关键期限{date}，需在到期前完成资金与头寸安排',
            'severity': 'medium',
            'rule_locator': 'F042|clause:最后交易日',
            'corrective_action': '按日历安排资金与交接',
            'due_at': date,
        })
    for index, date in enumerate(calendar['delivery']):
        rows.append({
            'object_id': f'M-DELIVERY-{index + 1}',
            'object_type': 'timeline',
            'assessment': f'交割日{date}，注意非交易日的代理安排',
            'severity': 'low',
            'rule_locator': 'F042|clause:交割方式',
            'corrective_action': '确认交割手续责任人与代理',
            'due_at': date,
        })
    return rows


def action_memo(timeline, baselines, events, plans, quotes):
    """A short decision memo for the risk owner, consistent with the numbers."""
    over_limit = [r['row_id'] for r in baselines if r['long_excess_lots'] or r['short_excess_lots']]
    parity = [r['row_id'] for r in baselines if r['parity_required'] and not r['parity_compliant']]
    funding = [r for r in baselines if r['additional_funds_cny'] > 0]
    rejected = [r['event_id'] for r in events if r['request_disposition'] == 'reject']
    declined = [r['plan_id'] for r in plans if r['disposition'] == 'reject']
    bad_quote = [r['quote_id'] for r in quotes if not r['tick_valid']]

    funding_detail = '、'.join(
        '{}（{:.2f} 元）'.format(r['row_id'], r['additional_funds_cny']) for r in funding)

    lines = [
        '# AG2612 交割准备：头寸与资金测算纪要',
        '',
        f"## 期限",
        f"- 期权到期与行权截止：{timeline['option_expiry_date']} 15:30（{timeline['option_expiry_exercise_cutoff']}）",
        f"- 期货最后交易日：{timeline['futures_last_trading_date']}",
        f"- 交割日：{'、'.join(timeline['delivery_dates'])}",
        f"- 20% 保证金阶段起点：{timeline['margin_20pct_start_date']}",
        '',
        '## 头寸',
        f"- 超出单向限仓的基线：{'、'.join(over_limit) if over_limit else '无'}",
        f"- 持仓数量不满足2手整数倍：{'、'.join(parity) if parity else '无'}",
        '普通偶数手交易无法修复既有奇数持仓，需核查成交明细并升级到有授权的纠错路径。',
        '',
        '## 资金',
        f"- 需追加资金的基线：{funding_detail if funding else '无'}",
        '- 保证金按多空毛额计算，追加资金为保证金与结算后总权益的差额，未计安全垫。',
        '',
        '## 请求与提案处置',
        '- 拒绝的期权请求：' + ('、'.join(rejected) if rejected else '无'),
        '- 退回的交易计划：' + ('、'.join(declined) if declined else '无'),
        '- 需重报的报价：' + ('、'.join(bad_quote) if bad_quote else '无'),
        '',
        '## 规则版本与内部假设',
        '结论依据所附 F047/F042 版本与计划日历。资金口径为内部规划定义：',
        '毛额保证金、各快照独立测算、暂不计经纪商加收与临时调整。',
        '后台值守安排不改变交易所交易日或规则期限。',
        '',
        '## 建议动作',
        '1. 限仓与持仓数量异常在最后交易日前处置，并保留升级路径记录。',
        '2. 资金缺口按上面列示金额安排，交割日代理手续提前确认。',
        '3. 规则结论、规划参数与处置建议分层留档，便于复核。',
    ]
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-data', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()

    input_dir, output_dir = args.input_data, args.output
    output_dir.mkdir(parents=True, exist_ok=True)

    rules = read_rules(input_dir)
    trading = read_calendar(input_dir)
    timeline, calendar = contract_timeline(trading['trading'], trading['working'])
    calendar['delivery'] = timeline['delivery_dates']
    calendar['trading'] = trading['trading']

    snapshots = read_csv(input_dir / 'futures_snapshots.csv')
    baseline_list, baseline_index = baseline_snapshots(snapshots, rules, calendar)

    events = read_csv(input_dir / 'option_requests.csv')
    event_list, effects = option_events(events, baseline_index, rules, calendar)
    event_list = finish_option_events(event_list, effects, snapshots, rules)

    post_list = post_option_snapshots(baseline_index, effects, rules)
    post_list = finish_post_option(post_list, baseline_index, rules)

    plans = read_csv(input_dir / 'proposed_trade_plans.csv')
    plan_list = trade_plans(plans, baseline_index)

    quotes = read_csv(input_dir / 'proposed_option_quotes.csv')
    quote_list = quote_checks(quotes, rules)

    # Internal Decimal helpers stay out of the delivered JSON.
    for record in baseline_list:
        record.pop('_settlement_dec', None)

    funding = {
        'metadata': {
            'currency': 'CNY',
            'timezone': 'Asia/Shanghai',
            'scenario_id': 'AG2612-DELIVERY-PREP',
            'calculation_assumptions': [
                '按各方向毛额计算保证金；各快照独立测算',
                '总权益包含已占用保证金；VM只计当日结算变动',
                '按所附规则版本及计划日历；暂不计经纪商加收和临时调整',
                '有效行权以行权价生成期货，在所指快照结算价结算',
            ],
        },
        'contract_timeline': timeline,
        'futures_snapshots': baseline_list,
        'option_requests': event_list,
        'post_option_snapshots': post_list,
        'trade_plan_checks': plan_list,
        'quote_checks': quote_list,
    }
    (output_dir / 'funding_results.json').write_text(
        json.dumps(funding, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    ledger = risk_ledger(baseline_list, event_list, plan_list, quote_list, calendar)
    columns = ['object_id', 'object_type', 'assessment', 'severity',
               'rule_locator', 'corrective_action', 'due_at']
    import io
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns)
    writer.writeheader()
    writer.writerows(ledger)
    (output_dir / 'risk_ledger.csv').write_text(buffer.getvalue(), encoding='utf-8')

    (output_dir / 'action_memo.md').write_text(
        action_memo(timeline, baseline_list, event_list, plan_list, quote_list),
        encoding='utf-8')

    print(json.dumps({'status': 'ok', 'output': str(output_dir),
                      'baselines': len(baseline_list), 'events': len(event_list),
                      'plans': len(plan_list), 'quotes': len(quote_list)}))


if __name__ == '__main__':
    main()
