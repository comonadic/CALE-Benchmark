# 资本债券审核资料

三份PDF保留完整原件及原有页码。F011与F014是同一发行人的不同资本层级、不同期次募集文件；F013是2026年6月末的存量特征表。客户草稿和核对清单供团队审核交接使用，核对值由审核人员根据原件填写。

物理页按阅读器从1计数，印刷页按原件页脚编号记录。募集条款引用对应“基本条款”，历史发行事件引用债务章节，六月存量引用CCA表行及具体工具列。涉及不同资料的推断请分别记录来源。引用范围应覆盖支持核对点所需的完整条款。

更正台账每个check_id一行。checked_value填写该核对点的结论，value_unit记录其单位：

| value_type | checked_value | value_unit |
|---|---|---|
| number | 阿拉伯数字，可含千分位 | 金额用CNY、CNY_10K、CNY_M或CNY_100M；比例用percent（百分数值）或ratio（小数）；其他用multiple、year、month、count、business_day |
| date | YYYY-MM-DD | date |
| monthday | MM-DD | monthday |
| bool | true或false | bool |
| enum | 清单choices中适用的代码 | enum |
| text | 名称、标识码、评级或报告月 | text、identifier、rating或month |

金额单位分别为人民币元、万元、百万元、亿元。认购金额和增发规模可以使用任何一种等值人民币单位。判断中的事实角色用evidence_role记录：

| evidence_role | 含义 |
|---|---|
| clause | 募集文件直接规定的条款或直接列示的事实 |
| reported_stock | 较早报告日CCA列示的存量事实 |
| disclosed_event | 募集文件回溯列示的发行事件 |
| calculation | 根据条款或表值作的换算、合计或上限计算 |
| inference | 跨文件身份配对、顺位比较或事实性质的推断 |
| not_confirmed | 所附资料尚不能确认的结果 |

source_refs采用文件ID、物理页、印刷页及条款/表格定位。rationale解释条款、证据角色和推理，client_impact说明相关结论影响客户的本金风险、现金安排、认购操作或沟通。一个核对点可以引用多份文件；涉及两类债券的共同条款请分别引用两份募集文件。
