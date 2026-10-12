# CALE Benchmark

金融与法律专业工作评测集，目前各 5 题，共 10 题。任务使用原生 Harbor 目录与 schema 1.3，以真实公开材料和工作底稿提出职业委托，交付可编辑的工作簿、文书、台账或分析文件。

`tasks/` 下每个目录是一道完整题目：题面、原件、解题环境、可执行参考解、独立评分环境、客观检查和专业 rubric。维护谱系在 lineage.json，原件与构造记录在 provenance/。来源文件保留原始机构身份；项目补充的业务参数分别记录出处。

| 任务 | 工作内容 |
|---|---|
| finance-pilot-01-v2 | 利润与经营现金流桥接、营运资本复核 |
| finance-pilot-02-v2 | 银行资本工具比较、原稿纠错与证据定位 |
| finance-pilot-03-v2 | REIT 分配模型、情景分析与交付审查 |
| finance-pilot-04-v2 | 期货期权交割与保证金操作安排 |
| finance-pilot-05-v2 | 审计整改金额、口径与状态对账 |
| legal-pilot-01-v2 | 合同及附件修订、谈判台账 |
| legal-pilot-02-v2 | 仲裁程序计划与期限工作簿 |
| legal-pilot-03-v2 | 限制条件下的并购价格审查 |
| legal-pilot-04-v2 | 证券行政处罚金额与责任分析 |
| legal-pilot-05-v2 | 专利无效证据台账与论证 |

## 运行

要求 Python 3.12+、Docker 和 Compose。框架固定 Harbor 0.17.1；解题 CLI 固定 Claude Code 2.1.296，公开镜像配方固定基础镜像 digest、Python 库和原生 CLI 包的 SHA-512。支持 x64/ARM64。

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/validate_task_package.py tasks/* --require-harbor
.venv/bin/python scripts/build_images.py --output runs/prepared
.venv/bin/python scripts/run_benchmark.py \
  --env-file /absolute/path/model.env \
  --images runs/prepared/images.json \
  --output runs/opus-5-5-first \
  --docker-host unix:///var/run/docker.sock
```

凭据文件使用 `ANTHROPIC_API_KEY` 和 `ANTHROPIC_BASE_URL`；也接受已有 Forge 的 `RSI_ANTHROPIC_BASE_URL`。Heju endpoint 为 `https://www.hejuapi.com`，模型为 `claude-opus-5-5`。密钥从运行时读取，不能提交仓库。自定义 Docker socket/config 或构建代理通过各脚本参数指定。

Runner 调用原生 Harbor `Job` 和 `claude-code` agent，每题一次独立尝试，默认并发 2、最多 60 轮、解题 2400 秒、评分 2100 秒，关闭 Job 自动重试。模型调用使用实际响应的 token usage；CLI 成本字段是其估计值，供应商账单另行核对。

## 环境与评分

Agent 镜像只含输入、工具和 CLI；开始时输出为空。参考解和 tests 不进入 agent 镜像。模型 endpoint 在 agent 阶段以运行时域名白名单开放，评分沙箱保持离线。文件产物由 Harbor 从 agent 环境导出并传入独立 verifier。

`tests/Dockerfile` 的构建上下文为该题 `tests/`，评分镜像自带 `/tests/test.sh` 和可信输入。`build_images.py` 分别构建两种角色；`run_benchmark.py` 在本次运行的 staging 副本里绑定真实镜像 ID 到原生 `task.toml`。规范任务保留公开可构建配方，仓库不写入宿主局部镜像 ID。独立 verifier 需要此镜像准备/绑定步骤；直接运行未经准备的 task 会缺少评分代码。

客观检查与开放式专业评阅共同聚合最终 reward。宿主桥接器只读取本次声明的 verifier 镜像产生的密封请求，将题面、可信输入、候选与私有 rubric 发给配置的评分模型，校验响应后写回。金融桥接保留原始 PDF 页面和候选引用证据。Judge 不接收参考解或预期分数。协议与恢复条件见 [评分桥接协议](scripts/rubric-bridge-protocol.md)。

Harbor 将数值 reward 写入 `/logs/verifier/reward.txt` 或 reward.json；完整分项报告、真实模型响应和轨迹在本次 `runs/` 目录。模型/协议故障保留为评分失败，不能据此报告候选零分。任务表现与运行故障分别统计；资源在每次 trial 结束或取消后清理。

## 验证状态与维护

源任务在入库前完成 10 次参考解、10 次空输出基线，以及专业校准与独立审阅。参考解得到的真实 reward 保留：其中金融第 4 题为 0.94，其余参考分数和校准依据由源批次报告记录。这个阶段验证执行与评分链路，独立模型解题结果另行保存；静态解析通过也不表示模型已解出题目。

本仓库的发布变更是在相同题面、输入、参考解和评分代码基础上补齐 Claude Code 依赖；`manifest.json` 记录发布差异。实际 Claude Code + Opus 5.5 首轮结果将在运行完成后更新到 reports/。

两份行业参考 skill 在 `skills/`，包括资料获取/筛选/抽取、题目设计、环境、参考解、评分器构造、谱系和批量验收方法。当前任务保留生成时的历史谱系，后续修改生成新版本。

目录结构和 reward 接口遵循 [Harbor task format](https://docs.harborframework.com/tasks/overview)。原始资料的发布机构、文件地址与哈希见各题的 provenance 和 lineage；这些原件的权利由原发布方保留。
