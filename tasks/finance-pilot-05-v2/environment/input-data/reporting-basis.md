# 审阅口径

报告信息时点为 2025-12-22。主报告总览明确截至 2025 年 9 月底；单项另载时间按原文记录，未列明单项截止日时注明“未单列”。原问题期间、整改措施时间和本次审阅日期分别保留。

金额采用人民币及原文口径。金额规范列使用亿元：1 万亿元 = 10000 亿元，1 亿元 = 10000 万元。原数值和原单位同时保留。未知、不适用和真实零分别表达；未知或不适用数字留空，原因写入 `evidence_limit`。

“已报告金额覆盖比”是对应主题已报告整改金额除以原问题金额。“披露差额”是两项披露规范金额的算术差。台账同时说明主体、地域与项目范围，供资金明细匹配和余额核查。公开报告的工程阶段与整改动作按其具体含义记录；银行回单、预算批准和工程验收分别作为进一步核验所需的证据层次。

`status` 表示证据状态，可采用：`reported_partial`（已报告部分进展）、`reported_progress`（有进展但无法定量判断闭环）、`reported_action_complete`（已报告某项动作完成）、`reported_plan`（计划或申请阶段）、`not_disclosed`（相关进展未单列）、`reported_summary`（汇总披露）、`closure_not_established`（当前证据尚不能建立闭环）、`not_applicable`（不适用）。具体动作、范围及闭环判断由解释列补充。

`mapping_type` 表示证据关系：`same_issue`（同事项主附件重述）、`subset`（子项）、`same_publication_only`（同次发布的不同事项）、`summary_check`（报告层勾稽）、`overview`（总体口径）。`aggregation_rule` 表示汇总处理：`do_not_sum`（当前缺互斥或同口径依据）、`subset_of_N01`（已包含于 N01）、`rounding_check_only`（报告数字勾稽）、`independent_department_scope`（部门事项另列）、`not_applicable`（不适用）。在解释列说明取值依据。

台账使用 O01、O02、N01、N01a、N02、N03、N04、N05、D01、D02、R01 共 11 个稳定主行，辅助行使用其他唯一 ID。
