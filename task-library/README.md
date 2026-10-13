# 任务类型库

本库记录真实工作流的调研结果。先选任务类型，再按 `input_data` 找材料。`verified` 表示工作、长程动作、可复核产物和软件参与有调研依据；运行环境、具体题目和评分仍须另行构造与验证。

2026-10-13 按用户要求从零重启调研。此前四张种子卡原样移至 [`_archive/2026-10-13-pre-research/`](./_archive/2026-10-13-pre-research/README.md)，不参加本批次准入和默认选卡。新卡追加新编号，保留历史 ID。

当前活动卡共11张（金融6、法律5；10张verified、1张candidate）。按审阅后的卡片补充的原件、输入覆盖和缺口见[任务卡材料资源库](../reference-library/README.md)。

| 行业 | 卡片 | 工作类型 | 状态 |
|---|---|---|---|
| 金融 | [FIN-F01-001](finance/F01/FIN-F01-001.yaml) | 最新财报下的三表联动模型更新 | verified |
| 金融 | [FIN-F02-001](finance/F02/FIN-F02-001.yaml) | IPO跨文件一致性核查与问询回复底稿 | verified |
| 金融 | [FIN-F03-002](finance/F03/FIN-F03-002.yaml) | 流贷需求测算与授信调查复核 | verified |
| 金融 | [FIN-F04-001](finance/F04/FIN-F04-001.yaml) | 到期及回售债券资金落实排查 | verified |
| 金融 | [FIN-F13-002](finance/F13/FIN-F13-002.yaml) | 期现敞口台账与套保效果复核 | verified |
| 金融 | [FIN-F17-001](finance/F17/FIN-F17-001.yaml) | 审计错报、更正与余额交接 | verified |
| 法律 | [LAW-L01-002](legal/L01/LAW-L01-002.yaml) | 合同审改与最终版本复核 | verified |
| 法律 | [LAW-L02-002](legal/L02/LAW-L02-002.yaml) | 证据编排、时间线与争点对应 | verified |
| 法律 | [LAW-L03-001](legal/L03/LAW-L03-001.yaml) | 尽调资料清单与缺口维护 | verified |
| 法律 | [LAW-L04-001](legal/L04/LAW-L04-001.yaml) | 债权申报和本金利息复核 | verified |
| 法律 | [LAW-L12-001](legal/L12/LAW-L12-001.yaml) | 国际仲裁程序时间表变更复核 | candidate |

每卡保留来源 URL、原始作者或机构、定位、简短摘要、核对日期及取得正文的方式。转载和镜像按原始来源合并计数。`excerpt` 为摘要，均未按逐字引文使用。

专家耗时是有限材料包下的研究估计；建议文件名用于说明产物形态。`software.provision` 是后续实例化的环境需求，不表示当前已经安装。市场、账户和法规版本用对应时点快照提供，采集与真实业务提交不包含在卡片工作中。候选卡保留具体缺口，默认不用于造题。

目前记录一个双向融合关系：同主体、同截止日且同材料条件下，FIN-F01-001 的营运资金、债务和现金流支持表可进入 FIN-F03-002 的独立授信复核。新增FIN-F02-001还记录了同主体审计调整卡FIN-F17-001作为上游的单向关系；实际组题仍须确认共用材料完整。其他卡保持空列表。

维护方法见两份行业 skill 的 `references/workflow-research.md`。批次范围、来源核验和待补项见 [调研记录](../research/workflows/2026-10-13/README.md)。

静态校验：

```bash
python -m pip install -r task-library/requirements.txt
python scripts/validate_task_library.py
```

校验检查 YAML、编号和目录、来源编号、证据原始来源及软件支持标记、状态和融合引用。它不代替对来源内容及专业判断的人工复核。
