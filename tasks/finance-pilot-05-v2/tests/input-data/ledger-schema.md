# 追踪台账字段

CSV 使用 UTF-8，首行包含下列英文列名，可增加解释列。数值列使用数值文本，空值留空，不使用千位分隔符或百分号。`coverage_pct` 使用百分数值，例如 12.34 表示 12.34%。

```text
item_id,title,scope,period,role,source_locator,related_locator,mapping_type,original_value,original_unit,original_yiyuan,progress_value,progress_unit,progress_yiyuan,disclosure_gap_yiyuan,coverage_pct,total_count,started_count,completed_count,other_count,calculation,status,aggregation_rule,evidence_limit,next_evidence,priority
```

`item_id` 和 `title` 标识事项；`scope` 记录责任主体、地域、资金类别及项目范围；`period` 记录原问题期间和整改时间；`role` 区分公开原问题、公开整改表述与审阅计算。`source_locator`、`related_locator` 使用文件 ID、物理页、印刷页及章节或表行；后者记录相关证据或关联主行。

`original_value`、`original_unit` 保留原披露核心基准。`progress_value`、`progress_unit` 保留对应进展。两者可以是金额、计数或百分比，按下列事项字段含义使用。`original_yiyuan`、`progress_yiyuan` 仅用于金额规范值。`disclosure_gap_yiyuan` 记录要求的金额披露差额；`coverage_pct` 记录适用的已报告金额覆盖比或工程阶段比例。每个计算在 `calculation` 保留表达式、输入依据与含义。

| 事项 | 数值字段用途 |
| --- | --- |
| O01 | original_value 为总览立行立改数量；progress_value、coverage_pct 为总览该类报告完成率；total_count 为总览三类问题合计。结语未整改计数、比例及其截止信息可放解释列或辅助行；也可在 other_count 记录结语未整改数并说明其具体含义。completed_count 可留空；填写条件完成数时，须标明条件复算及其口径假设，分别保留原文事实与计算结果 |
| O02 | original_value、original_unit 为共整改问题金额的原值与单位 |
| N01、N02 | original_value 为原问题金额；progress_value 为对应公开进展金额；差额与覆盖比用于披露比较 |
| N01a | original_value 为沉淀子项金额；total_count 为子项项目数；进展金额按该子项披露情况填写 |
| N03 | original_value、total_count 为原问题项目数；progress_value 为公开整改涉及资金 |
| N04 | original_value、total_count 为原未完成任务河段数；progress_value、started_count 为列示已开工阶段数；completed_count、other_count 分别为完工和前期阶段数；coverage_pct 为完工阶段占比。另在 calculation 或增加列记录其余阶段占比 |
| N05 | original_value、total_count 为原逾期项目数；progress_value 为公开开（完）工合并数；other_count 为未列入合并类别的差额；coverage_pct 为合并阶段覆盖比。started_count、completed_count 按分阶段披露情况填写 |
| D01 | original_value 为闲置资金；对应金额进展按披露情况填写 |
| D02 | original_value 为闲置财政资金；申请预算与其单位换算写入 calculation 或增加解释列 |
| R01 | original_value 为主报告该节汇总；progress_value 为三个披露分项算术和；disclosure_gap_yiyuan 为汇总减分项和 |

`status`、`mapping_type`、`aggregation_rule` 使用审阅口径里的标签。`evidence_limit` 说明当前证据支持范围与待核实事项。`next_evidence` 记录补证责任方、具体材料、闭环判据及建议期限。`priority` 使用 high、medium、low，并在解释列给出理由。引用、推理和补证安排允许采用不同的合理措辞和顺序。

O01 可增加 `reported_unrectified_count`、`reported_unrectified_pct`、`conditional_completed_count`、`conditional_completion_pct` 等列，也可在现有解释列或唯一辅助行表达这些信息。上述附加列不属于必需字段；数值必须同时说明披露位置、截止口径及实际披露或条件计算的角色。两处统计不能直接勾稽时，保留原文并列明需取得的统计底表。
