# 2026-10-13 RSI Forge 候选题包快照

**本批计划 10 题，收集到 9 份候选题包，完整验收 0/10。** 本目录供查看题面、材料、代码和真实运行结果；尚不能作为已验收评测集使用。FIN-F02-001 没有产出题包。

造题使用 **Claude Code + claude-opus-5-5**，独立试解使用 **Codex + gpt-6.1-sol**。题目细节、材料可行性判断和范围收缩均由各自造题 Job 决定。本次只是发布已保留的结果，没有启动新的造题或试解。

## 题目长什么样

各题围绕职业交付物展开：从给定原件中取数、核对期间与版本、建立可编辑工作簿或文书，并留下引证和资料缺口。输入不足时，题面把结论限制在公开披露复核或准备工作，不把缺失的内部底稿写成已取得事实。全部通过脚本处理 Office/PDF，不需要 CUA。

| 任务卡 / 题面 | 当前工作范围 | 最终交付物 | 原生验证现状 |
|---|---|---|---|
| [FIN-F01-001：更新海大集团三表模型](tasks/FIN-F01-001/instruction.md) | 2025 年报与 2026 半年报；合并历史数据及 2026H2 分析情景 | 联动三表 XLSX、模型说明 PDF | 参考解评分断言数量不一致；空输出评分器异常 |
| [FIN-F02-001](../../task-library/finance/F02/FIN-F02-001.yaml) | 本批未收集到候选题包 | — | 未产出 |
| [FIN-F03-002：桌面授信调查预审](tasks/FIN-F03-002/instruction.md) | 海大集团公开财报、套保公告和股东会决议 | 营运资金测算 XLSX、调查预审 PDF | 评分镜像缺少 tests/input-data，未进入原生试跑 |
| [FIN-F04-001：次月到期或回售债券偿债资金排查](tasks/FIN-F04-001/instruction.md) | 申万宏源债券披露、财报、新疆证监局通知及排查模板 | 偿债排查 XLSX、资金风险说明 PDF | 参考解脚本路径错误；空输出评分器异常 |
| [FIN-F13-002：2026H1 套期保值披露复核](tasks/FIN-F13-002/instruction.md) | 海大集团半年报、授权及套保政策等四份原件 | 披露复核 XLSX、复核备忘录 PDF | 评分器 trusted source anchor missing；未得到有效分数 |
| [FIN-F17-001：现金流列报收尾复核与证据交接](tasks/FIN-F17-001/instruction.md) | 茂名石化实华 2025 年报；区分公开披露与项目底层证据 | 证据和缺口 CSV、复核备忘录 PDF | 参考解 1.0；空输出评分器异常；Codex 11/24 |
| [LAW-L01-002：采购合同修订与签署前审查](tasks/LAW-L01-002/instruction.md) | 采购合同、需求文件和招标原件 | 带真实修订与批注的 DOCX、清洁合同、审查意见 | 参考解 1.0、空输出 0.0；两次 Codex 均异常退出，未完成最终文档 |
| [LAW-L02-002：公开诉讼披露线索编排与补件复核](tasks/LAW-L02-002/instruction.md) | 重庆建工 2026-08-22 公告中的 23 起案件线索 | 案件/金额/补件 XLSX、证据目录及补件说明 PDF | 参考解 1.0、空输出 0.0；Codex 11/34 |
| [LAW-L03-001：收购项目尽调需求与缺口台账](tasks/LAW-L03-001/instruction.md) | 国城矿业收购披露、两期法律意见及审计报告等七份原件 | 24 个工作单元的尽调台账 XLSX、缺口摘要 PDF | 评分镜像缺少 tests/environment/input-data，未进入原生试跑 |
| [LAW-L04-001：破产债权申报准备与缺口核查](tasks/LAW-L04-001/instruction.md) | 震鑫磁业管理人申报指引和三份空白表单 | 计息工作簿、待补全申报书 PDF、证据目录 PDF | 评分镜像缺少 tests/input-data，未进入原生试跑 |

## 可以直接看的样例

- [三表模型题面](tasks/FIN-F01-001/instruction.md)：从年报与半年报建立历史数据、公式联动和明确标注性质的情景模型。Job 留下的[工作簿](tasks/FIN-F01-001/three_statement_model.xlsx)和[说明 PDF](tasks/FIN-F01-001/model_update_notes.pdf)是候选参考产物，当前评分验证未通过。
- [合同修订题面](tasks/LAW-L01-002/instruction.md)：交付含真实 Word 修订/批注的合同、清洁稿和审查意见；参考解和空白基线已分别取得 1.0、0.0，但独立 Codex 尚未完成最终文档。
- [诉讼线索整理题面](tasks/LAW-L02-002/instruction.md)：把公告中的 23 起案件编入台账，核对金额与页码，并列补件。Job 留下的[工作簿](tasks/LAW-L02-002/evidence_workbook.xlsx)、[证据目录](tasks/LAW-L02-002/evidence_catalog.pdf)和[补件说明](tasks/LAW-L02-002/supplementation_note.pdf)可直接查看。独立 Codex 实际得分为 11/34。

## 文件与证据

`tasks/<任务卡>/` 保存原生 Harbor schema 1.3 目录，包括题面、`task.toml`、`environment/Dockerfile`、真实 `environment/input-data/` 文件、`solution/solve.sh`、参考解脚本、`tests/Dockerfile`、评分器、断言与谱系。这里提交的是实际文件，不依赖本机路径、ZIP 下载或 Git LFS 指针。

`evidence/<任务卡>/` 保存静态检查、构建/评分反馈，以及按生产 attempt 区分的原生试跑记录和实际输出。历史版本的运行结果不能用来证明当前版本已通过；具体版本与 attempt 见 [batch.json](batch.json)。评分失败保留为失败或无分数，不计作零分。

31 个 agent 输入文件均与此前提供的原始材料字节一致，见[输入哈希记录](evidence/input-file-hashes.json)。原材料来源和授权/使用边界沿用仓库[资源库记录](../../reference-library/batches/2026-10-13-task-inputs/README.md)。

题包中的 `authoring_status = ready/verified/validated`、完成总结或局部测试声明来自造题 Job，按原样保留，**不代表本批验收结论**。本批统一状态以此目录和 `batch.json` 为准：9 份通过静态/Harbor schema 检查，0 份完成最终验收；仍有构建、参考解入口、评分器异常、独立试解及专业质量验证缺口。

此次发布仅排除 Python/LibreOffice 缓存；题面、材料、参考解、镜像配方和评分代码未修改。执行证据中的本机安装路径被替换为占位标签。原文件与导出对应关系见 [export-provenance.json](export-provenance.json)，发布文件哈希见 [SHA256SUMS.json](SHA256SUMS.json)。模型会话、数据库、检查点及凭据未入库。原始快照继续保留在生产工作区。

本批未加入仓库默认 `tasks/` 评测集。后续修复须产生可追溯的新候选版本，再完成真实构建、参考解与空白基线、独立试解和 skill 要求的完整验证。
