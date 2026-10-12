# 造题交付契约：原生 Harbor

本页用于实际造题交付。行业调研、采集与筛选仍可独立完成。题目以给定 input-data 为起点，由 agent 选择职业问题、instruction 和交付物。

**本页每条规则要么由 `scripts/validate_task_package.py` 检查，要么不写。**无法机器校验的规则不构成契约，只构成建议。

## 可运行的目录

```text
<task_id>/
  instruction.md
  task.toml
  environment/
    Dockerfile
    input-data/                     # 进入 /workspace/input-data 的实际文件
  solution/
    solve.sh                        # 可执行参考解，输出到 /workspace/output
    build_reference.py              # 派生式参考解的实际实现
    ...                             # 参考解所需代码/私有资源
  tests/
    Dockerfile                      # 独立评分环境的可构建配方
    test.sh                         # 实际评分入口
    assertions.json                 # 断言契约：S、断言清单、关键错误 cap
    grade.py                        # 评分实现（按断言产出报告）
    ...                             # 事实依据、rubric 与评分依赖
  lineage.json
  private/
    provenance.json                 # 各输入的原件地址/哈希、复制或转换方式
    authoring/                      # 选题、原件复核与独立 review 记录
    evaluation/validation.json      # 分层验证记录
```

基础约定遵循 [Harbor task format](https://docs.harborframework.com/tasks/overview)。`private/` 和 lineage 是维护附录；可执行入口必须是原生 Harbor 文件。单独写 environment manifest、rubric 或自定义 task.yaml 不构成可运行交付。

`private/` 下的文件**不得**出现在 `environment/` 构建上下文或任何进入解题视图的路径中。provenance 记录中不得写入作者机器的绝对路径。

## instruction 与可见输入

用自然的职业工作请求说明角色、业务背景、资料、工作动作和产物。以 `/workspace/input-data/` 和 `/workspace/output/` 等实际容器路径描述工作，与 Dockerfile、oracle 和评分器保持一致。

**题面公开的交付要求必须与 `tests/assertions.json` 的断言集合一一对应。**验证器检查题面未要求的内容 = 隐藏要求，属缺陷。作者完成断言后须反向核对题面：新增断言必须同步修订题面。

产物的格式、必需字段、时间/口径和检索范围应在题面公开。只固定互操作必需的字段，不因作者偏好的表序、布局或措辞否定合理交付。

题面应当**要求分批落盘**：让产物在工作过程中逐步累积，而不是要求一次性产出。理由：候选的工作时长不构成评分依据，评分只看终态存在的产物；增量落盘使"做了多少"与"写了多少"解耦，避免个别环节卡住导致已完成的工作全部丢失。

场景设定和参数可写成正常的项目背景、工作底稿与分析假设。出题过程、采集说明、合成步骤、私有评分权重与运行状态放作者记录或 provenance；题面不反复宣告"合成题""培训演练"，也不堆叠与工作无关的否定句。官方原件保留真实身份，补充底稿与官方文件分别溯源。材料不足的事实以本项工作的待核实事项呈现。

题目不靠遗漏必要输入、隐藏口径或猜已提供的裁判/披露结果制造难度。

## 材料的组合合理性

材料包的验收标准不是体积，而是三条性质：

1. **功能必要性**：每份文件都有职业流程上的功能，不是为便于解题而补的辅助说明。判定：删掉该文件，交付要求是否仍能从其余材料合理完成？是则它不必要。
2. **集合自洽性**：期间、口径、主体边界、单位、版本能相互对上；冲突与差异须是**真实材料本有的**（待核实的勾稽差、条款冲突、重述前后），不是作者制造的。
3. **职业形状**：文件组合是真实从业者手上会有的东西（审计底稿像底稿，投研材料像投研材料）。**禁止"作者添加剂"**：为让某事实易于查找而补的方便文档、为讲清口径而加的说明文件、为增加难度而加的障碍文档。

原始材料中已存在的模糊性、勾稽差异与条款冲突应当保留。真实的亏损、差异与冲突不天然等于低质量材料。

## task.toml 与环境

从 [配置模板](../assets/task.toml) 填入真实元信息、时间预算、资源与网络策略，按实际安装的 Harbor schema 解析。Dockerfile 声明所需应用、库、字体和工作目录，复制实际输入并创建空输出目录。依赖有可复现版本，代码不依赖作者机器的绝对路径或私有运行库。

`[agent].timeout_sec` 是**题目声明的预算**，必须与断言数量、材料规模、预期工作项数相称。两小时（7200 秒）是长程题的参考上限；预算不应作为制造难度的手段——**难度来自材料规模、勾稽层数与约束耦合，不来自把预算压到刚好不够**。

解题镜像只包含运行工具与输入。solution、tests、答案和私有作者材料由对应阶段提供，不能经 Docker COPY、隐藏工作表、批注或文件属性进入解题视图。Harbor 使用独立 verifier 时，评分镜像需自带 `/tests/test.sh` 及其依赖，另附可构建的评分镜像配方和准备方法；运行时绑定实际角色镜像。

**目标运行时的适配层单独存放。**题包本体是 Harbor 原生格式；rsi-forge 等 runner 的配置属于运行适配层，不写入题包，也不代替题目的环境定义。

## 参考解

`solution/solve.sh` 在干净环境**实际生成**全部交付物。

**参考解必须是派生式的。**`solve.sh` 调用 `build_reference.py`，从 `input-data/` 重新计算并生成产物，不得用 `cp` 复制预制字节。理由：复制式 oracle 只能证明"参考字节存在"，无法证明"题目从可见输入可解"，使 `harbor_execution` 验证层失效。只有需要不可复算的原生格式（手工排版、扫描件标注）时才允许预置字节，并在 provenance 中说明理由。

参考解所需代码与资源均在包内。实际参考文件应可打开，关键取数、计算、引用与推理有可复核证据。工作簿公式可重算；DOCX 修改位置与附件联动可审阅。

**参考解在真实评分中得到的分数应当保留为真实分数。**正确参考解获得少量扣分时，检查是题面、原件、参考解、抽取器还是 rubric 的问题，不为了追求满分而改成迎合评阅者的答案。

## 评分

评分契约见 [评分器构造](scorer-construction.md)。落盘要求如下，**这是 runner 读取的唯一契约**：

- `tests/assertions.json` 声明 `scale`（S）、断言清单与 `critical_errors`。
- `tests/test.sh` 是唯一评分入口，调用 `tests/grade.py`。
- `grade.py` 写入：
  - `/logs/verifier/report.json` — 完整分项报告，含每条断言的 `id` / `status` / 实际值 / 期望值，以及 `reward`、`P`、`S`、`valid`、`status`。
  - `/logs/verifier/reward.json` — `{"reward": <有限数值>}`，供 runner 直接读取。

**只写 `reward.json`。**不写 `reward.txt`：单一来源避免两个文件不一致时的歧义，也与 rsi-forge 的 `report.json` 断言协议同构。

`report.json` 的 `status` 取值必须区分四类，**不得混淆**：

| status | 含义 | 是否进有效分母 |
|---|---|---|
| `graded` | 完整有效评分 | 是 |
| `graded_candidate_defect` | 候选产物缺失/损坏，按实际内容评了分 | 是 |
| `verifier_failure` | 评分依赖或协议故障，**未产生 reward** | 否 |
| `not_run` | 未运行 | 否 |

缺文件、解析错误、未运行或评阅故障**不能转成满分**；评分器故障**不能转成候选零分**。运行前清除旧 reward，旧 reward 绝不能掩盖本次失败。

评阅者使用题面、可见输入、实际产物和 rubric 独立评分；oracle 或挑战标签、期望分数留在验收侧。**评阅分不得突破结果断言上界，也不得为已被客观判定为错误的主张给正分。**

文件结构检查、关键词出现或参考答案 hash 相同，不能替代专业正确性。

## 谱系与实际验证

`private/provenance.json` 记录各输入的原件地址/哈希、复制或转换方式、版本与必要场景设定。`lineage.json` 记录实际证据范围、材料角色、任务类型/动作、多父关系与变更；同源变体继承划分组。批次配额与调度机制由批次配置维护。

`lineage.json` schema 在全部题目间统一，字段集合由 `validate_task_package.py` 检查。

交付前在声明的环境中运行 Harbor：参考解生成与评分、空输出基线、击中关键业务错误的挑战，以及任务允许的合理替代解。核验环境内可编辑性、公式重算、输入/答案隔离及运行后资源回收。审查或检查发现缺陷时，同步修订题面、输入、参考解、断言和谱系，再重跑受影响验证。

验证记录见 [验证](verification.md)；分层状态写入 `private/evaluation/validation.json`。

## 构造方法与模板

环境、参考解、评分器与批量验收分别见 [环境构造](environment-construction.md)、[参考解](reference-solution.md)、[评分器](scorer-construction.md)、[批量生产](batch-production.md)。assets 中的 shell 模板规定接口，需要作者在包内实现 `build_reference.py` / `grade.py`；模板本身不是完整参考解或评分器。

运行 `python scripts/validate_task_package.py <task目录> --require-harbor` 做静态检查，再按验证方法执行实际运行。
