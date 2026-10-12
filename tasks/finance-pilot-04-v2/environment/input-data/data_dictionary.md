# 输入字段与关系

futures_snapshots.csv：row_id为唯一快照；participant_type的customer对应客户，non_futures_member对应非期货公司会员。long_lots/short_lots为同交易编码AG2612各方向一般持仓，不得净额限仓。价格单位CNY/千克，权益单位CNY。

option_requests.csv：event_id唯一；base_row_id指向资金/持仓基础；call/put为买方看涨/看跌，exercise/abandon为申请类型。时间均为UTC+08:00。各批次不同且已付权利金。请求有效性与形成期货后的合规/资金压力是两层结论。

proposed_trade_plans.csv：TP各计划独立；open_long/open_short/close_long/close_short数量均为手，0代表没有该交易动作；先检查每笔非零动作再检查计划后持仓。

proposed_option_quotes.csv：premium_cny_per_kg为拟申报权利金报价，quantity_lots为期权手数。要求检查最小变动价位与1 tick资金价值，不执行报价。

planning_calendar.csv：is_trading_day/is_working_day为基准交易日/交割业务工作日，0/1表示否/是；按calendar-notice-basis.md的年度公告与常规周末推算，暂不计未来临时调整。desk_operations_open为内部后台日常值守，operations_note为替代办理安排；该列不参与规则交易日计数。11月24日基准是交易/工作日，常规后台暂停另行安排代理办理。

规则文件：F047原生DOCX与其完整正文/表格可读副本；F042原HTML与正文可读副本。F047的Pn/TABLEn是原word/document.xml内w:body直接子节点的0-based块索引，段落和表格一起计数，P表示段落块；不是页码、条款编号或仅按段落计数的连续编号。表格Rn为0-based行索引。F042以HTML表格行标题定位。引用可用条款/表行名称，不必生成或猜测DOCX页码。
