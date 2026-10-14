# 验证记录

包版本：`LAW-L04-001` 初稿。参考产物由包内 `solution/build_reference.py` 从环境可见的四份官方原件派生生成；本机生成后复制到包根作为 Harbor 预期 `/workspace/output` 的本地映射。

- 静态包检查：passed。检查器输出位于交付会话日志；`validate_task_package.py` 检查必需文件、24 条断言、lineage、reward plumbing、派生式入口和环境输入隔离。Harbor Python 包不可用，Harbor schema：not_available。
- 参考生成：passed。工作簿、申报书 PDF、证据目录 PDF 均从原件重新生成。PDF 用 pypdf 抽取中文字正常。
- 工作簿公式：passed。LibreOffice 对空值公式重算；独立扰动副本以 2026-08-01 至 2026-09-02（截止不含）、本金 10,000、年率 12% 复算出 32 天及 106.67 元。
- 参考评分：passed，24/24（1.0），报告见 `private/evaluation/local-reference-report.json`。
- 空输出基线：passed，0/24（0.0），缺交付状态为 `graded_candidate_defect`。
- 关键错误挑战：错误计息截止日被 `CALC.exclusive-cutoff` 命中并触发 0.5 cap，实际 23/24、reward 0.5。
- 合理替代解枚举：not_run。
- Harbor Docker 构建与实际 Harbor runner 执行：not_run；当前环境 Harbor CLI 不存在，Docker daemon 不可用。
- 独立 solver rollout、人工专业判断评阅：not_run。

状态保持 draft；静态与本地参考链验证不等同 Harbor 执行、独立试解或专业判断校准。
