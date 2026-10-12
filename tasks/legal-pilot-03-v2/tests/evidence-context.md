Judge-only evidence index; original input remains authoritative.
{
  "version": 2,
  "source_hash": "1181a1b2244a3d078ec76a930acde94a750239743c84b556b660cb65c2f073b2",
  "facts": [
    {
      "id": "E-SCOPE",
      "role": "regulatory_decision",
      "source": "L034",
      "locator": "P31, HTML 六、审查决定开头",
      "proposition": "要求集中双方和集中后实体履行六项义务；具体第三项文字限定集中后实体",
      "supports": [
        "控制台主体范围",
        "实施记录事项边界"
      ]
    },
    {
      "id": "E-O1",
      "role": "operative_obligation",
      "source": "L034",
      "locator": "P32 / 六（一）",
      "proposition": "现有客户合同全部商业条款继续履行，例外是客户因自身原因实质违约、客户自行终止或要求修改",
      "scenario": [
        "P01",
        "P02"
      ],
      "inference": "不能凭集中统一政策减损折扣；客户自主终止应证据化核验后办理，而非强迫继续"
    },
    {
      "id": "E-O2",
      "role": "operative_obligation",
      "source": "L034",
      "locator": "P33 / 六（二）",
      "proposition": "服务不低于交易前，维护标准、画面质量和数据反馈仅为非穷尽例子",
      "scenario": [
        "P03"
      ],
      "inference": "三个业务指标下调均触发暂停；其他可证明不下降的技术替代可审"
    },
    {
      "id": "E-O3",
      "role": "operative_obligation_with_open_implementation_detail",
      "source": "L034",
      "locator": "P34 / 六（三）",
      "proposition": "没有正当理由，各城市年度实际成交价不超过生效日前24个月分众/新潮各自对应城市实际成交价",
      "scenario": [
        "P04-SH",
        "P04-CD",
        "P04-BJ",
        "P04-GZ"
      ],
      "inference": "分城分主体代理不能混合、择高或直接代法定唯一基准；北京6%为未证实声称；计划不是实际"
    },
    {
      "id": "E-O4",
      "role": "operative_obligation",
      "source": "L034",
      "locator": "P35 / 六（四）",
      "proposition": "公平合理无歧视，保留没有正当理由，不拒供、搭售或不合理条件限制自由选择",
      "scenario": [
        "P05"
      ],
      "inference": "删除影院必购；真实合理理由需证据，不能将所有条件绝对禁止"
    },
    {
      "id": "E-O5",
      "role": "operative_obligation",
      "source": "L034",
      "locator": "P36 / 六（五）",
      "proposition": "放弃已订立生效独家全部相关权利；新签/续签不得独家、自动续约",
      "scenario": [
        "P06",
        "P07"
      ],
      "inference": "原生效独家行权及违约金停止；新/续签去掉两类条款；不无依据宣布所有其他合同约定失效"
    },
    {
      "id": "E-O6",
      "role": "operative_obligation",
      "source": "L034",
      "locator": "P37 / 六（六）",
      "proposition": "完善制度、体系、定期培训，正文未规定具体频率",
      "scenario": [
        "P08"
      ],
      "inference": "FAQ不能证明体系完备，季度或其他合理频率为内部设计，不是法定期限"
    },
    {
      "id": "E-REPORT",
      "role": "operative_obligation_and_attachment_scope",
      "source": "L034",
      "locator": "P29,P38 / 五、六末段",
      "proposition": "2026-09-18承诺方案有法律约束力；自生效起每年向监管报告直至条件终止",
      "scenario": [
        "P09"
      ],
      "inference": "年度循环与证据包；具体报送日期/期间/格式须取得附件校准，不能仅2027一次"
    },
    {
      "id": "E-RELEASE",
      "role": "operative_obligation",
      "source": "L034",
      "locator": "P39 / 五年期满段",
      "proposition": "五年期满后可申请，监管据市场竞争决定是否解除；批准前继续履行",
      "scenario": [
        "P09"
      ],
      "inference": "2031-10-09可作内部周年标记，无批准不能自动停止"
    },
    {
      "id": "E-SUPERVISION",
      "role": "regulatory_power",
      "source": "L034",
      "locator": "P40",
      "proposition": "可通过监督受托人或自行检查；违反可依法处理",
      "supports": [
        "S1统一资料响应、保全、整改控制"
      ]
    },
    {
      "id": "E-EFFECT",
      "role": "operative_effective_date",
      "source": "L034",
      "locator": "P41,P44",
      "proposition": "自公告日起生效，落款2026-10-09",
      "supports": [
        "合成筛查历史窗口"
      ]
    },
    {
      "id": "E-BACKGROUND",
      "role": "regulatory_finding_not_raw_market_dataset",
      "source": "L034",
      "locator": "P18-P19 / 四（一）",
      "proposition": "份额为区间50%-55%、5%-10%、55%-60%；HHI2672→3644，Δ972",
      "inference": "不反推更精确份额或未提供竞争者组成；不是提案合规充分证据"
    },
    {
      "id": "E-BUSINESS",
      "role": "business_information_and_calculation_assumption",
      "source": "operations-scenario.md,price-ledger.csv,price-plan.csv",
      "locator": "筛查口径、12提案ID、条款A/B/C、各transaction_id",
      "proposition": "统一屏幕周，净金额已扣折扣退款且不含税；2027年度计划；运营提案和价格台账为交办资料。",
      "inference": "客观计算可唯一复核；规范执行口径和正当理由保留证据化条件判断"
    }
  ],
  "calculations": [
    {
      "baseline": 100.0,
      "plan": 95.0,
      "diff": -5.0,
      "pct": -0.050000000000000044,
      "n": 2,
      "units": 300.0,
      "amount": 30000.0,
      "city": "上海",
      "historical_operator": "分众",
      "role": "internal_screening_calculation",
      "formula": "sum(net_revenue_cny in date window/city/operator) / sum(units in same scope); plan revenue/units; delta = plan-base; pct=plan/base-1",
      "window": "2024-10-09 <= screen_date < 2026-10-09",
      "reference_locator": "compliance-control.xlsx 价格筛查, 上海/分众行",
      "legal_limit": "不是法定唯一基准，计划不是实际年度价格"
    },
    {
      "baseline": 90.0,
      "plan": 95.0,
      "diff": 5.0,
      "pct": 0.05555555555555558,
      "n": 2,
      "units": 200.0,
      "amount": 18000.0,
      "city": "上海",
      "historical_operator": "新潮",
      "role": "internal_screening_calculation",
      "formula": "sum(net_revenue_cny in date window/city/operator) / sum(units in same scope); plan revenue/units; delta = plan-base; pct=plan/base-1",
      "window": "2024-10-09 <= screen_date < 2026-10-09",
      "reference_locator": "compliance-control.xlsx 价格筛查, 上海/新潮行",
      "legal_limit": "不是法定唯一基准，计划不是实际年度价格"
    },
    {
      "baseline": 66.66666666666667,
      "plan": 58.0,
      "diff": -8.666666666666671,
      "pct": -0.13000000000000012,
      "n": 2,
      "units": 300.0,
      "amount": 20000.0,
      "city": "成都",
      "historical_operator": "分众",
      "role": "internal_screening_calculation",
      "formula": "sum(net_revenue_cny in date window/city/operator) / sum(units in same scope); plan revenue/units; delta = plan-base; pct=plan/base-1",
      "window": "2024-10-09 <= screen_date < 2026-10-09",
      "reference_locator": "compliance-control.xlsx 价格筛查, 成都/分众行",
      "legal_limit": "不是法定唯一基准，计划不是实际年度价格"
    },
    {
      "baseline": 60.0,
      "plan": 58.0,
      "diff": -2.0,
      "pct": -0.033333333333333326,
      "n": 2,
      "units": 200.0,
      "amount": 12000.0,
      "city": "成都",
      "historical_operator": "新潮",
      "role": "internal_screening_calculation",
      "formula": "sum(net_revenue_cny in date window/city/operator) / sum(units in same scope); plan revenue/units; delta = plan-base; pct=plan/base-1",
      "window": "2024-10-09 <= screen_date < 2026-10-09",
      "reference_locator": "compliance-control.xlsx 价格筛查, 成都/新潮行",
      "legal_limit": "不是法定唯一基准，计划不是实际年度价格"
    },
    {
      "baseline": 110.0,
      "plan": 120.0,
      "diff": 10.0,
      "pct": 0.09090909090909083,
      "n": 2,
      "units": 200.0,
      "amount": 22000.0,
      "city": "北京",
      "historical_operator": "分众",
      "role": "internal_screening_calculation",
      "formula": "sum(net_revenue_cny in date window/city/operator) / sum(units in same scope); plan revenue/units; delta = plan-base; pct=plan/base-1",
      "window": "2024-10-09 <= screen_date < 2026-10-09",
      "reference_locator": "compliance-control.xlsx 价格筛查, 北京/分众行",
      "legal_limit": "不是法定唯一基准，计划不是实际年度价格"
    },
    {
      "baseline": 100.0,
      "plan": 120.0,
      "diff": 20.0,
      "pct": 0.19999999999999996,
      "n": 2,
      "units": 200.0,
      "amount": 20000.0,
      "city": "北京",
      "historical_operator": "新潮",
      "role": "internal_screening_calculation",
      "formula": "sum(net_revenue_cny in date window/city/operator) / sum(units in same scope); plan revenue/units; delta = plan-base; pct=plan/base-1",
      "window": "2024-10-09 <= screen_date < 2026-10-09",
      "reference_locator": "compliance-control.xlsx 价格筛查, 北京/新潮行",
      "legal_limit": "不是法定唯一基准，计划不是实际年度价格"
    },
    {
      "baseline": 50.0,
      "plan": 52.0,
      "diff": 2.0,
      "pct": 0.040000000000000036,
      "n": 2,
      "units": 200.0,
      "amount": 10000.0,
      "city": "广州",
      "historical_operator": "分众",
      "role": "internal_screening_calculation",
      "formula": "sum(net_revenue_cny in date window/city/operator) / sum(units in same scope); plan revenue/units; delta = plan-base; pct=plan/base-1",
      "window": "2024-10-09 <= screen_date < 2026-10-09",
      "reference_locator": "compliance-control.xlsx 价格筛查, 广州/分众行",
      "legal_limit": "不是法定唯一基准，计划不是实际年度价格"
    },
    {
      "baseline": null,
      "plan": 52.0,
      "diff": null,
      "pct": null,
      "n": 0,
      "units": 0.0,
      "amount": 0.0,
      "city": "广州",
      "historical_operator": "新潮",
      "role": "internal_screening_calculation",
      "formula": "sum(net_revenue_cny in date window/city/operator) / sum(units in same scope); plan revenue/units; delta = plan-base; pct=plan/base-1",
      "window": "2024-10-09 <= screen_date < 2026-10-09",
      "reference_locator": "compliance-control.xlsx 价格筛查, 广州/新潮行",
      "legal_limit": "不是法定唯一基准，计划不是实际年度价格"
    }
  ],
  "excluded_transactions": [
    {
      "id": "OUT-SH",
      "reason": "2024-10-08 在起点前"
    },
    {
      "id": "POST-SH",
      "reason": "2026-10-09 是生效日，不属于生效日前窗口"
    }
  ],
  "expected_deliverables": [
    "/workspace/output/compliance-control.xlsx",
    "/workspace/output/implementation-record.md"
  ],
  "reference_is_unique_answer": false
}
