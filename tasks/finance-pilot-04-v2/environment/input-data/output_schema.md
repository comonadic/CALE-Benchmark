# 交付结构

`risk_ledger.csv`使用UTF-8，必有列：object_id, object_type, assessment, severity, rule_locator, corrective_action, due_at。object_id覆盖所有R/O/TP/Q输入对象及四项日期里程碑，允许一对象多行。object_type分别用futures_snapshot、option_request、trade_plan、option_quote、timeline；四项里程碑各有至少一条timeline行，其object_id可自选。assessment给出具体判断和量化差额，不能只写通过/失败；due_at使用ISO日期/带时区日期时间，或明确的业务触发点（例如新增交易前、订单放行前、立即升级）。截止时间是否包含边界在assessment说明。

`funding_results.json`使用以下顶层字段（数值为JSON number，不附单位字符串）：

- metadata: currency, timezone, scenario_id, calculation_assumptions。
- contract_timeline: option_expiry_date, option_expiry_exercise_cutoff, futures_last_trading_date, delivery_dates（数组）, margin_20pct_start_date。
- futures_snapshots: 每个R行一对象，字段row_id, margin_rate, directional_limit_lots, long_lots, short_lots, long_excess_lots, short_excess_lots, parity_required（boolean）, parity_compliant（boolean）, variation_margin_cny, equity_after_vm_cny, required_margin_cny, additional_funds_cny, calculation_trace。
- option_requests: 每个O行一对象，字段event_id, time_and_inventory_valid（boolean）, request_disposition（exercise/abandon/reject）, added_long_lots, added_short_lots, incremental_vm_cny, reason。
- post_option_snapshots: R03/R11各一对象，字段base_row_id, applied_event_ids（数组）, long_lots, short_lots, long_excess_lots, short_excess_lots, incremental_vm_cny, equity_after_vm_cny, required_margin_cny, additional_funds_cny, calculation_trace。
- trade_plan_checks: 每个TP一对象，字段plan_id, transaction_lot_parity_valid（boolean）, resulting_long_lots, resulting_short_lots, resulting_long_excess_lots, resulting_short_excess_lots, resulting_position_parity_valid（boolean）, disposition, reason。disposition取以下之一：approve（可直接执行）、approve_with_controls（可执行但须同时落实资金或头寸控制）、reject（不可执行）、review（须升级核查后决定）；处置理由写在reason。
- quote_checks: 每个Q一对象，字段quote_id, tick_valid（boolean）, one_lot_tick_value_cny, quoted_quantity_tick_value_cny, nearest_lower_valid_quote, nearest_upper_valid_quote。

calculation_trace可以用公式字符串、操作数/引用ID字典或逐步计算列表；应使金额与输入能够重新计算，不能只有结果。额外字段允许；数组顺序无要求。字段值和名称可以用英文，说明用中文。

`action_memo.md`应含按期限排序的处理安排、需核查事项的处置、期权请求有效性与行权后的限仓/资金区分、期权到期与期货最后交易/交割区分、原件条款/表格引用及所用资金规划假设。应说明规则依据与运营待核定安排。
