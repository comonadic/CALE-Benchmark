Judge-only evidence index; original input remains authoritative.
{
  "version": 2,
  "source": {
    "document_id": "L041",
    "sha256": "0357bd3dcd783574afb5a052662f699b494ae7e394ddccbd54bf459ba8eac630",
    "input": "/workspace/input-data/L041-original.html",
    "paragraph_index": "direct detail-news p positions"
  },
  "evidence": [
    {
      "id": "E01",
      "role": "regulatory-finding",
      "locator": "P15",
      "finding": "2020关联赠与90%股权及同一63,973,167.75元科目影响",
      "support": "relation disclosure omitted; total profit not net profit; do not triple-count loss"
    },
    {
      "id": "E02",
      "role": "regulatory-finding",
      "locator": "P18",
      "finding": "年度虚增收入/利润及业务主体年度区别",
      "support": "Beijing Zhongguangyang 2021–2023 services vs two marketing subsidiaries 2022; no allocations"
    },
    {
      "id": "E03",
      "role": "task-assumption-and-calculation",
      "locator": "交办背景与口径.md; P15、P18",
      "finding": "八项反推",
      "formula": "point=a/(p/100); D in (a/((p+0.005)/100),a/((p-0.005)/100)]",
      "rows": [
        {
          "ratio_id": "R01",
          "year": 2020,
          "numerator_label": "关联赠与交易金额",
          "numerator": 63973167.75,
          "percentage_points": 142.3,
          "denominator": "当期披露净资产",
          "point_estimate": 44956547.962052,
          "lower_exclusive": 44954968.37778012,
          "upper_inclusive": 44958127.6573316,
          "locator": "P15",
          "limitation": "仅条件数学估计，不是精确年报金额"
        },
        {
          "ratio_id": "R02",
          "year": 2020,
          "numerator_label": "虚增利润总额",
          "numerator": 63973167.75,
          "percentage_points": 471.03,
          "denominator": "当期披露利润总额",
          "point_estimate": 13581548.46825043,
          "lower_exclusive": 13581404.30116658,
          "upper_inclusive": 13581692.63839499,
          "locator": "P15",
          "limitation": "仅条件数学估计，不是精确年报金额"
        },
        {
          "ratio_id": "R03",
          "year": 2021,
          "numerator_label": "虚增营业收入",
          "numerator": 43712098.4,
          "percentage_points": 16.29,
          "denominator": "当期披露营业收入",
          "point_estimate": 268337006.75260895,
          "lower_exclusive": 268254669.53053084,
          "upper_inclusive": 268419394.53484803,
          "locator": "P18",
          "limitation": "仅条件数学估计，不是精确年报金额"
        },
        {
          "ratio_id": "R04",
          "year": 2021,
          "numerator_label": "虚增利润总额",
          "numerator": 4529090.07,
          "percentage_points": 5.07,
          "denominator": "当期披露利润总额绝对值",
          "point_estimate": 89331165.0887574,
          "lower_exclusive": 89243154.08866996,
          "upper_inclusive": 89419349.85192497,
          "locator": "P18",
          "limitation": "绝对值不能推出正负号，不能称净利润"
        },
        {
          "ratio_id": "R05",
          "year": 2022,
          "numerator_label": "虚增营业收入",
          "numerator": 151418026.84,
          "percentage_points": 49.44,
          "denominator": "当期披露营业收入",
          "point_estimate": 306266235.5177994,
          "lower_exclusive": 306235265.12286377,
          "upper_inclusive": 306297212.17760694,
          "locator": "P18",
          "limitation": "仅条件数学估计，不是精确年报金额"
        },
        {
          "ratio_id": "R06",
          "year": 2022,
          "numerator_label": "虚增利润总额",
          "numerator": 11992778.71,
          "percentage_points": 13.49,
          "denominator": "当期披露利润总额绝对值",
          "point_estimate": 88901250.63009636,
          "lower_exclusive": 88868312.04149686,
          "upper_inclusive": 88934213.64479052,
          "locator": "P18",
          "limitation": "绝对值不能推出正负号，不能称净利润"
        },
        {
          "ratio_id": "R07",
          "year": 2023,
          "numerator_label": "虚增营业收入",
          "numerator": 164224867.76,
          "percentage_points": 40.64,
          "denominator": "当期披露营业收入",
          "point_estimate": 404096623.4251968,
          "lower_exclusive": 404046912.9290196,
          "upper_inclusive": 404146346.15479267,
          "locator": "P18",
          "limitation": "仅条件数学估计，不是精确年报金额"
        },
        {
          "ratio_id": "R08",
          "year": 2023,
          "numerator_label": "虚增利润总额",
          "numerator": 17837345.39,
          "percentage_points": 27.61,
          "denominator": "当期披露利润总额绝对值",
          "point_estimate": 64604655.5233611,
          "lower_exclusive": 64592958.13869274,
          "upper_inclusive": 64616357.14544467,
          "locator": "P18",
          "limitation": "绝对值不能推出正负号，不能称净利润"
        }
      ]
    },
    {
      "id": "E04",
      "role": "regulatory-categorization",
      "locator": "P16、P19–P28",
      "finding": "八人责任范围",
      "people": [
        {
          "name": "金铉玉",
          "position": "2020年4月起 财务总监",
          "years": "2021–2023",
          "finding": "根据李某安排参与案涉行为；签署2021–2023年年度报告",
          "category": "直接负责的主管人员",
          "defense": "事实不清、证据不足；不知悉未参与；职权有限且已勤勉；处罚偏重，请求从轻或减轻",
          "response": "证据相互印证；按指令划转资金；组建工作群讨论划款方案；财务总监签字保证但未勤勉尽责",
          "fine": 3000000,
          "ban": 3,
          "locator": "P19、P28、P29、P31、P40、P44",
          "followup": "调取具体划款指令、审批权限和群聊原始记录，核对监管所述参与行为与勤勉措施。"
        },
        {
          "name": "朱文龙",
          "position": "2020年8月–2023年7月 副总经理；2020年12月–2023年7月 副董事长",
          "years": "2021–2022",
          "finding": "分管北京中广阳并参与案涉行为；签署2021–2022年年度报告",
          "category": "直接负责的主管人员",
          "defense": "事实认定错误；无主观故意；处罚过重，请求从轻或减轻",
          "response": "董事、副总经理分管北京中广阳并参与；签字保证2021、2022年报；构成未勤勉尽责",
          "fine": 3000000,
          "ban": 3,
          "locator": "P20、P28、P29、P32、P40、P44",
          "followup": "调取分工文件、北京中广阳业务审批及董事会质询资料；回应参与和管理职责，不仅凭否认故意。"
        },
        {
          "name": "肖自然",
          "position": "2020年11月–2022年10月 董秘；2020年7月–2023年8月 总经理；2023年8月–2024年9月 董事长",
          "years": "2021–2023",
          "finding": "任职期间未有效管理和关注经营情况；签署2021–2023年年度报告",
          "category": "直接负责的主管人员",
          "defense": "无知情权限和实际认知；未实际履职；按内部流程签字，请求从轻、减轻或免罚",
          "response": "虽不知情、未实际履职，但签字保证相关年报足以证明未勤勉尽责；量罚适当",
          "fine": 1500000,
          "ban": 0,
          "locator": "P21、P28、P29、P33、P41",
          "followup": "调取履职范围、取得信息的请求与障碍记录、年报审阅和异议记录；不将不知情直接等同免责。"
        },
        {
          "name": "曹放",
          "position": "2020年12月–2023年7月 董事长",
          "years": "2021–2022",
          "finding": "未审慎了解和关注经营情况；签署2021–2022年年度报告",
          "category": "直接负责的主管人员",
          "defense": "被动担任董事长；未参与任何经营；量罚过重，请求减轻",
          "response": "说明和证据不足以证明勤勉尽责；量罚适当",
          "fine": 1500000,
          "ban": 0,
          "locator": "P22、P28、P29、P34、P41",
          "followup": "调取董事会审议、质询和风险提示处理记录；补证须对应勤勉义务履行。"
        },
        {
          "name": "包笠",
          "position": "2019年11月–2022年10月 董事",
          "years": "2020",
          "finding": "参与无偿赠与事项；签署2020年年度报告",
          "category": "其他直接责任人员",
          "defense": "不知悉未参与；主持会议和签字系本职工作；处罚不公平，请求免罚",
          "response": "参与相关事项、主持相关董事会审议；说明和证据不足以证明勤勉；量罚适当",
          "fine": 1500000,
          "ban": 0,
          "locator": "P16、P27、P29、P35、P41",
          "followup": "调取赠与审议资料、关联关系识别及披露审核记录；任期重叠不能扩成全部年度责任。"
        },
        {
          "name": "任希宁",
          "position": "2022年11月–2023年12月 北京至谋总经理",
          "years": "2022–2023",
          "finding": "根据李某安排参与北京中广阳案涉行为，直接导致2022–2023年年报虚假记载；决定未称其签署年报",
          "category": "其他直接责任人员",
          "defense": "被动参与、按公司要求实施、主观恶性小，请求从轻",
          "response": "参与2022–2023年业务单据编制和匹配资金冒充回款，直接导致违法；量罚适当",
          "fine": 1000000,
          "ban": 0,
          "locator": "P23、P28、P29、P36、P42",
          "followup": "调取单据制作者、指令链和回款匹配流水；岗位在北京至谋与参与北京中广阳不能混同。"
        },
        {
          "name": "王能海",
          "position": "2023年8月–2024年8月 总经理",
          "years": "2023",
          "finding": "未有效管理公司；签署2023年年度报告",
          "category": "其他直接责任人员",
          "defense": "未参与日常经营、已尽力履职、无故意和过错、量罚过重，请求减轻或免罚",
          "response": "履职受限仍签字保证2023年报，证明未勤勉；认定和处罚程序符合法律规定",
          "fine": 500000,
          "ban": 0,
          "locator": "P12、P24、P28、P29、P37、P43",
          "followup": "调取履职受限材料、年报审查和异议记录；未要求听证不等于未作申辩。"
        },
        {
          "name": "王北",
          "position": "2018年起 业务总监",
          "years": "2022",
          "finding": "根据李某安排参与博铭锐创、汉诺睿雅案涉行为，直接导致2022年年报虚假记载；决定未称其签署年报",
          "category": "其他直接责任人员",
          "defense": "未参与业务洽谈、合同签订、无划款权限且已勤勉，请求免罚",
          "response": "参与2022年度业务单据编制和资金循环，直接导致违法；量罚适当",
          "fine": 500000,
          "ban": 0,
          "locator": "P25、P28、P29、P38、P43",
          "followup": "调取两子公司单据编制与资金循环分工记录；无划款权限不能消除其他参与路径。"
        }
      ]
    },
    {
      "id": "E05",
      "role": "party-defense",
      "locator": "P29",
      "finding": "个人否认/受限等是申辩，不直接作确认事实"
    },
    {
      "id": "E06",
      "role": "regulatory-response",
      "locator": "P30–P38",
      "finding": "接受部分合理申辩未具体指向；逐人的不采纳理由公开"
    },
    {
      "id": "E07",
      "role": "regulatory-disposition",
      "locator": "P12、P39–P44",
      "finding": "八人警告；罚款合计12500000元；仅金、朱三年禁入；公司李某前期处罚金额未知"
    },
    {
      "id": "E08",
      "role": "procedural-statement",
      "locator": "P12、P44–P45",
      "finding": "王能海未要求听证但申辩；禁入从宣布，缴罚/救济从收到；实际日期缺失"
    },
    {
      "id": "E09",
      "role": "material-gap",
      "locator": "P26 + inventory",
      "finding": "仅列证据类型，不提供底层材料；补证建议不是已取得证据"
    },
    {
      "id": "E10",
      "role": "internal-draft-correction-targets",
      "locator": "内部核查初稿.docx S01–S12",
      "targets": [
        {
          "id": "S01",
          "locator": "P12、P26",
          "reason": "监管认定与作者直接验证须分层。不得假称有完整卷宗。"
        },
        {
          "id": "S02",
          "locator": "P15",
          "reason": "保留认定归属和信息披露缺陷；不能把交易披露等同关联属性已披露。"
        },
        {
          "id": "S03",
          "locator": "P15",
          "reason": "科目影响不是三个独立损失，决定未提供净利润、税影响或损害基数。"
        },
        {
          "id": "S04",
          "locator": "P15、P18",
          "reason": "参见金额核查表R01至R08。即使假定唯一调整，利润总额仍须分别考虑正负分支；本报告不作真实报表重述。"
        },
        {
          "id": "S05",
          "locator": "P18",
          "reason": "年度金额未分摊到三家子公司；不凭汇总数字量化单人或单子公司贡献。"
        },
        {
          "id": "S06",
          "locator": "P16、P19–P25、P27–P28",
          "reason": "法定角色、任职、签字及参与路径分别记录，不能由任期推定全部责任。"
        },
        {
          "id": "S07",
          "locator": "P29–P38",
          "reason": "可以提出有依据的进一步核查或不同分析，但不得改写公开决定结论。"
        },
        {
          "id": "S08",
          "locator": "P23、P25、P36、P38",
          "reason": "岗位主体与行为主体、年度与签字证据不能混写。"
        },
        {
          "id": "S09",
          "locator": "P12、P29、P37",
          "reason": "程序事实按公开文本记录。缺送达、听证记录，不能全面复核程序合法性。"
        },
        {
          "id": "S10",
          "locator": "P12、P40–P44",
          "reason": "行政处罚与禁入对象和内容分别核对，本文不另行测算法定罚款。"
        },
        {
          "id": "S11",
          "locator": "P44–P45",
          "reason": "网页时间、宣布日期和收到日期有不同用途。须索取宣布、送达或收件凭证后才能计算。"
        },
        {
          "id": "S12",
          "locator": "P26–P28、P39–P44",
          "reason": "不扩大专业结论；补证计划应对应具体争点与实际记录。"
        }
      ]
    }
  ]
}
