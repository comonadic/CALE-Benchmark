# 法律 Benchmark 参考

借鉴任务结构、证据标注和评价机制，重新使用本土真实材料构建题目。英文 benchmark 中的法律或财务约定不自动适用于国内场景。

## [ALE](https://agents-last-exam.org/)

参考机制：专业工作与可检查的产物。借鉴真实角色、材料环境、工具操作与交付验收；本项目是受 ALE 启发的独立资料工作台。

## [CUAD](https://www.atticusprojectai.org/cuad/)

参考机制：合同条款标注。借鉴专家定义的条款类别和证据跨度，用于审查与风险矩阵设计。

## [MAUD](https://github.com/The-Atticus-Project/maud)

参考机制：并购协议理解。借鉴交易条款、例外与条件关系的细粒度问题设计。

## [ContractNLI](https://stanfordnlp.github.io/contract-nli/)

参考机制：合同命题与证据。区分文本支持、矛盾和未提及；让每个判断对应证据片段。

## [LegalBench](https://github.com/HazyResearch/legalbench)

参考机制：法律推理任务拆分。参考任务分类和评价结构；移植到国内任务时重新选择适用规范。

## [CAIL2018](https://github.com/china-ai-law-challenge/CAIL2018)

参考机制：中文法律文书结构。参考事实与裁判结果的字段分离；进一步扩展为证据核查和文书交付。

## [WorkForge · v1](https://arxiv.org/html/2610.04906v1)

参考机制：从材料到任务的工作流。参考原始材料、工作区、题面与验证器的分阶段组织。该论文已撤回，此处仅保留 v1 方法参考。

## 使用方式

为任务设计记录“借鉴机制、对应工作步骤、重新构造的输入、独立验证方法”。直接使用公开样例时标注来源与划分；不要作为新造的独立测试题。
