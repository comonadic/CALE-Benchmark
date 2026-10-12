# 分配测算工作簿交接数据字典

财务模型交接索引：按稳定业务名称检索、调整活动输入和复核结果，不依赖页面标签及布局。

工作簿级名称，不区分大小写，每个名称直接引用该工作簿现有工作表的一个单元格；不得引用多格区域、外部文件、常量或命名公式。名称可指向任意sheet/cell；业务标签可在数值上方、下方或任意合适位置，措辞自由。

金额统一用所选存值单位；metric_amount_scale为存值转人民币元的正倍率，metric_share_scale为存值转份数的正倍率。两个倍率可省，默认1，即人民币元和份。例如元/万元/百万元的金额倍率分别1/10000/1000000，份/万份/亿份的份数倍率分别1/10000/100000000。每份金额始终元/份、比例始终0至1小数，不缩放。展示格式可另设但须标单位。

可用 Excel/LibreOffice 的名称管理器建立区域；Python 可用 openpyxl 的 DefinedName，其他工具可写原生 workbook defined names。名称只负责定位，不能替代真实取数、公式和财务解释。

| 名称 | 业务含义 | 必需 | 角色 | 单位 | 符号/有效范围 |
|---|---|---|---|---|---|
| metric_np | 合并净利润 | 是 | source | 人民币元（存值乘amount_scale） | 有符号金额 |
| metric_da | 折旧和摊销 | 是 | source | 人民币元（存值乘amount_scale） | 调增金额 |
| metric_interest | 利息支出 | 是 | source | 人民币元（存值乘amount_scale） | 调增金额 |
| metric_tax | 所得税费用 | 是 | source | 人民币元（存值乘amount_scale） | 调增金额 |
| metric_ebitda_control | 披露基金EBITDA | 是 | source | 人民币元（存值乘amount_scale） | 披露控制数 |
| metric_wc | 应收应付项目变动 | 是 | source | 人民币元（存值乘amount_scale） | 有符号调整 |
| metric_other | 其他调增项 | 是 | source | 人民币元（存值乘amount_scale） | 调增金额 |
| metric_capex | 购买不动产等资本支出 | 是 | source | 人民币元（存值乘amount_scale） | 可存负调减额，或正支出额并在桥接中扣减 |
| metric_principal | 偿还借款本金 | 是 | source | 人民币元（存值乘amount_scale） | 同上 |
| metric_cash_interest_tax | 支付利息及所得税 | 是 | source | 人民币元（存值乘amount_scale） | 同上 |
| metric_old_reserve | 原未来支出预留 | 是 | source | 人民币元（存值乘amount_scale） | 同上；已包含在历史锚点内 |
| metric_d_control | 披露可供分配金额 | 是 | source | 人民币元（存值乘amount_scale） | 披露控制数 |
| metric_revenue | 项目公司营业收入 | 是 | source | 人民币元（存值乘amount_scale） | 收入下降驱动；不是基金收入 |
| metric_cash_in | 项目经营现金流入 | 是 | source | 人民币元（存值乘amount_scale） | 非负金额 |
| metric_cash_out | 项目经营现金流出 | 是 | source | 人民币元（存值乘amount_scale） | 非负支出金额 |
| metric_cash_control | 披露项目经营现金净流量 | 是 | source | 人民币元（存值乘amount_scale） | 披露控制数 |
| metric_fund_cash | 基金经营现金净流量 | 是 | source | 人民币元（存值乘amount_scale） | 基金口径 |
| metric_fund_income | 基金本期收入 | 是 | source | 人民币元（存值乘amount_scale） | 基金口径 |
| metric_shares | 基金份额总额 | 是 | source | 份（存值乘share_scale） | 正份数 |
| metric_project_ebitda | 项目公司EBITDA | 按说明可选 | source | 人民币元（存值乘amount_scale） | 项目口径 |
| metric_actual_paid | 本期实际分配金额 | 按说明可选 | source | 人民币元（存值乘amount_scale） | 非负金额 |
| metric_ratio | 最低分配比例 | 按说明可选 | source | 比例小数 | 0至1的小数 |
| metric_management_fee | 本期计提基金管理费 | 按说明可选 | source | 人民币元（存值乘amount_scale） | 正费用金额 |
| metric_custody_fee | 本期计提基金托管费 | 按说明可选 | source | 人民币元（存值乘amount_scale） | 正费用金额 |
| metric_operator_fee | 本期计提运营管理费 | 按说明可选 | source | 人民币元（存值乘amount_scale） | 正费用金额 |
| metric_selector | 活动情景选择器 | 是 | input | 文字或整数 | 整数1/2/3，或基准/压力/自定义文字 |
| metric_custom_decline | 自定义收入下降率 | 是 | input | 比例小数 | 0至1，含两端 |
| metric_custom_reserve | 自定义新增预留 | 是 | input | 人民币元（存值乘amount_scale） | 非负金额 |
| metric_proposed_input | 拟分配额原始输入 | 是 | input | 人民币元（存值乘amount_scale） | 非负金额；0有效；留空不可当作0 |
| metric_D | 活动情景原始可供分配金额D | 是 | formula | 人民币元（存值乘amount_scale） | 保留负值 |
| metric_positive | 活动正向可分配额 | 按说明可选 | formula | 人民币元（存值乘amount_scale） | 非负；若与upper是同一业务单元格可省此名称 |
| metric_lower | 90%分配下限 | 是 | formula | 人民币元（存值乘amount_scale） | 非负金额 |
| metric_upper | 100%分配上限 | 是 | formula | 人民币元（存值乘amount_scale） | 非负金额 |
| metric_per_unit | 正向每份可分配金额 | 是 | formula | 元/份，不缩放 | 元/份，非负 |
| metric_proposed | 经校验的活动拟分配额 | 是 | formula | 人民币元（存值乘amount_scale） | 输入为非负数时采用原输入；0有效；空白、非数值或负值时显示不可用，保留raw输入便于修正。允许名称指向已有校验金额格，不要求新增固定位置。 |
| metric_upper_margin | 拟分配额对上限余量 | 是 | formula | 人民币元（存值乘amount_scale） | 上限减拟分配额；可为负 |
| metric_lower_margin | 拟分配额对下限余量 | 是 | formula | 人民币元（存值乘amount_scale） | 拟分配额减下限；可为负 |
| metric_decision | 活动分配状态及输入不足原因 | 是 | formula | 文字或整数 | 清楚的业务文字，自由措辞 |
| metric_budget | 新增预留总预算 | 是 | formula | 人民币元（存值乘amount_scale） | 有符号预算，或0下界预算加单列缺口 |
| metric_remaining | 扣除当前新增预留后的剩余空间 | 是 | formula | 人民币元（存值乘amount_scale） | 同上 |
| metric_budget_gap | 总预算缺口 | 按说明可选 | formula | 人民币元（存值乘amount_scale） | 采用0下界且总预算原本为负时须提供；非负缺口 |
| metric_remaining_gap | 剩余预算缺口 | 按说明可选 | formula | 人民币元（存值乘amount_scale） | 采用0下界且剩余预算原本为负时须提供；非负缺口 |
| metric_historical | 历史复算可供分配金额 | 是 | formula | 人民币元（存值乘amount_scale） | 有符号金额 |
| metric_ebitda | 复算基金EBITDA | 是 | formula | 人民币元（存值乘amount_scale） | 基金合并口径 |
| metric_pre_reserve | 扣原预留前金额 | 是 | formula | 人民币元（存值乘amount_scale） | 基金合并口径 |
| metric_project_cash | 复算项目现金净流量 | 是 | formula | 人民币元（存值乘amount_scale） | 流入减流出 |
| metric_scope_difference | 基金减项目现金净流量差额 | 是 | formula | 人民币元（存值乘amount_scale） | 基金减项目，有符号 |
| metric_historical_per_unit | 历史可供分配每份金额 | 按说明可选 | formula | 元/份，不缩放 | 元/份；可选单列 |
| metric_ebitda_variance | EBITDA复算对披露差额 | 是 | formula | 人民币元（存值乘amount_scale） | 复算减披露 |
| metric_d_variance | 可供分配金额复算对披露差额 | 是 | formula | 人民币元（存值乘amount_scale） | 复算减披露 |
| metric_cash_variance | 项目现金复算对披露差额 | 是 | formula | 人民币元（存值乘amount_scale） | 复算减披露 |

可选命名区域 `metric_amount_scale` 与 `metric_share_scale` 均为一个有限正数单元格；省略时取1。

30个业务名称各指向15组合的D或上限余量结果。可以矩阵、长表、纵向分块等任意布局；行列坐标、标题文字和轴与数值距离不限。d00/d05/d10/d15/d20表示收入下降百分数；r0/r500/r1000表示新增预留万元。两类结果必须为真实公式并引用对应业务输入。

| 名称 | 收入下降 | 新增预留（元） | 结果 |
|---|---|---|---|
| metric_sensitivity_D_d00_r0 | 0% | 0 | 该组合的原始D |
| metric_sensitivity_margin_d00_r0 | 0% | 0 | 该组合拟分配额对100%上限余量 |
| metric_sensitivity_D_d00_r500 | 0% | 5,000,000 | 该组合的原始D |
| metric_sensitivity_margin_d00_r500 | 0% | 5,000,000 | 该组合拟分配额对100%上限余量 |
| metric_sensitivity_D_d00_r1000 | 0% | 10,000,000 | 该组合的原始D |
| metric_sensitivity_margin_d00_r1000 | 0% | 10,000,000 | 该组合拟分配额对100%上限余量 |
| metric_sensitivity_D_d05_r0 | 5% | 0 | 该组合的原始D |
| metric_sensitivity_margin_d05_r0 | 5% | 0 | 该组合拟分配额对100%上限余量 |
| metric_sensitivity_D_d05_r500 | 5% | 5,000,000 | 该组合的原始D |
| metric_sensitivity_margin_d05_r500 | 5% | 5,000,000 | 该组合拟分配额对100%上限余量 |
| metric_sensitivity_D_d05_r1000 | 5% | 10,000,000 | 该组合的原始D |
| metric_sensitivity_margin_d05_r1000 | 5% | 10,000,000 | 该组合拟分配额对100%上限余量 |
| metric_sensitivity_D_d10_r0 | 10% | 0 | 该组合的原始D |
| metric_sensitivity_margin_d10_r0 | 10% | 0 | 该组合拟分配额对100%上限余量 |
| metric_sensitivity_D_d10_r500 | 10% | 5,000,000 | 该组合的原始D |
| metric_sensitivity_margin_d10_r500 | 10% | 5,000,000 | 该组合拟分配额对100%上限余量 |
| metric_sensitivity_D_d10_r1000 | 10% | 10,000,000 | 该组合的原始D |
| metric_sensitivity_margin_d10_r1000 | 10% | 10,000,000 | 该组合拟分配额对100%上限余量 |
| metric_sensitivity_D_d15_r0 | 15% | 0 | 该组合的原始D |
| metric_sensitivity_margin_d15_r0 | 15% | 0 | 该组合拟分配额对100%上限余量 |
| metric_sensitivity_D_d15_r500 | 15% | 5,000,000 | 该组合的原始D |
| metric_sensitivity_margin_d15_r500 | 15% | 5,000,000 | 该组合拟分配额对100%上限余量 |
| metric_sensitivity_D_d15_r1000 | 15% | 10,000,000 | 该组合的原始D |
| metric_sensitivity_margin_d15_r1000 | 15% | 10,000,000 | 该组合拟分配额对100%上限余量 |
| metric_sensitivity_D_d20_r0 | 20% | 0 | 该组合的原始D |
| metric_sensitivity_margin_d20_r0 | 20% | 0 | 该组合拟分配额对100%上限余量 |
| metric_sensitivity_D_d20_r500 | 20% | 5,000,000 | 该组合的原始D |
| metric_sensitivity_margin_d20_r500 | 20% | 5,000,000 | 该组合拟分配额对100%上限余量 |
| metric_sensitivity_D_d20_r1000 | 20% | 10,000,000 | 该组合的原始D |
| metric_sensitivity_margin_d20_r1000 | 20% | 10,000,000 | 该组合拟分配额对100%上限余量 |

必需名称缺失、坏引用或重复名称将无法完成模型交接。金额、公式与分配状态需保持业务口径一致；文件或计算环境异常应在交接说明中说明。

本字典提供业务接口及单位，不提供年报取数值或测算结果。
