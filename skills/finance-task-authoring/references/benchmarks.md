# 金融 Benchmark 参考

借鉴任务结构、证据标注和评价机制，重新使用本土真实材料构建题目。英文 benchmark 中的法律或财务约定不自动适用于国内场景。

## [ALE](https://agents-last-exam.org/)

参考机制：专业工作与可检查的产物。借鉴真实角色、材料环境、工具操作与交付验收；本项目是受 ALE 启发的独立资料工作台。

## [FinQA](https://github.com/czyssrs/FinQA)

参考机制：证据与计算程序。把取数证据和运算链分别保存，用确定性计算验证数值。

## [ConvFinQA](https://github.com/czyssrs/ConvFinQA)

参考机制：多轮数值推理。借鉴对上一轮事实和计算结果的依赖设计，把变更请求做成连续工作。

## [TAT-QA](https://github.com/NExTplusplus/TAT-QA)

参考机制：表格与文本联合取证。围绕同一财报中的表格、正文和单位建立跨区域证据。

## [FinanceBench](https://github.com/patronus-ai/financebench)

参考机制：答案的文档与页码定位。公开仓库提供 150 条标注样例；借鉴答案、解释与原页证据的连接方式。

## [WorkForge · v1](https://arxiv.org/html/2610.04906v1)

参考机制：从材料到任务的工作流。参考原始材料、工作区、题面与验证器的分阶段组织。该论文已撤回，此处仅保留 v1 方法参考。

## 使用方式

为任务设计记录“借鉴机制、对应工作步骤、重新构造的输入、独立验证方法”。直接使用公开样例时标注来源与划分；不要作为新造的独立测试题。
