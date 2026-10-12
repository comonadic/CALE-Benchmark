# 造题交付契约：原生 Harbor

本页用于实际造题交付。行业调研、采集与筛选仍可独立完成。题目以给定 input-data 为起点，由 agent 选择职业问题、instruction 和交付物。

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
    ...                             # 参考解所需代码/私有资源
  tests/
    Dockerfile                      # 独立评分环境的可构建配方
    test.sh                         # 实际评分入口
    ...                             # 评测器、事实依据、rubric 与评分依赖
  lineage.json
  private/
    provenance.json
    authoring/                      # 选题、原件复核与独立 review 记录
    evaluation/                     # 证据、参考产物与验证记录
```

基础约定遵循 [Harbor task format](https://docs.harborframework.com/tasks/overview)。`private/` 和 lineage 是维护附录；可执行入口必须是原生 Harbor 文件。单独写 environment manifest、rubric 或自定义 task.yaml 不构成可运行交付。

## instruction 与可见输入

用自然的职业工作请求说明角色、业务背景、资料、工作动作和产物。以 `/workspace/input-data/` 和 `/workspace/output/` 等实际容器路径描述工作，与 Dockerfile、oracle 和评分器保持一致。产物的格式、必需字段、时间/口径和检索范围应在题面公开。

场景设定和参数可写成正常的项目背景、工作底稿与分析假设。出题过程、采集说明、合成步骤、私有评分权重与运行状态放作者记录或 provenance；题面不反复宣告“合成题”“培训演练”，也不堆叠与工作无关的否定句。官方原件保留真实身份，补充底稿与官方文件分别溯源。材料不足的事实以本项工作的待核实事项呈现。

题目不靠遗漏必要输入、隐藏口径或猜已提供的裁判/披露结果制造难度。引用范围和文件结构按职业用途设计；只固定互操作必需的字段，不因作者偏好的表序、布局或措辞否定合理交付。

## task.toml 与环境

从 [配置模板](../assets/task.toml) 填入真实元信息、时间预算、资源与网络策略，按实际安装的 Harbor schema 解析。Dockerfile 声明所需应用、库、字体和工作目录，复制实际输入并创建空输出目录。依赖有可复现版本，代码不依赖作者机器的绝对路径或私有运行库。

解题镜像只包含运行工具与输入。solution、tests、答案和私有作者材料由对应阶段提供，不能经 Docker COPY、隐藏工作表、批注或文件属性进入解题视图。Harbor 使用独立 verifier 时，评分镜像需自带 `/tests/test.sh` 及其依赖，另附可构建的评分镜像配方和准备方法；运行时绑定实际角色镜像。Forge 或其他宿主的配置是运行适配层，不能代替题目的环境定义。

## 参考解与评分

`solution/solve.sh` 在干净环境实际生成全部交付物；其代码或参考资源均在包内。实际参考文件应可打开，关键取数、计算、引用与推理有证据。工作簿公式可重算；DOCX 修改位置与附件联动可审阅。

原生交付的格式与布局元数据从原件读取；重算副本用于验证计算结果，审阅证据保留两者的身份与哈希。

`tests/test.sh` 对实际候选产物执行评分，并写 `/logs/verifier/reward.txt` 或有效 reward.json。按 rubric 分项计算权重，保留分项结果、理由和证据；缺文件、解析错误、未运行或 judge 故障不能转成满分。

评阅者使用题面、可见输入、实际产物和rubric独立评分；oracle或挑战标签、期望分数留在验收侧。

客观事实、计算、结构与文件完整性用可执行检查；开放式判断按证据化 rubric 使用明确配置的专业评阅通道。评分需要的库、模型/接口或外部宿主通道属于验证依赖，要随交付说明并实际接通。文件结构检查、关键词出现或参考答案 hash 相同，不能替代专业正确性。接受有依据的替代措辞、布局和论证。

## 谱系与实际验证

`provenance.json` 记录各输入的原件地址/哈希、复制或转换方式、版本与必要场景设定。`lineage.json` 记录实际证据范围、材料角色、任务类型/动作、多父关系与变更；同源变体继承划分组。批次配额与调度机制由批次配置维护。

交付前在声明的环境中运行 Harbor：参考解生成与评分、空输出基线、击中关键业务错误的挑战，以及任务允许的合理替代解。核验环境内可编辑性、公式重算、输入/答案隔离及运行后资源回收。审查或检查发现缺陷时，同步修订题面、输入、参考解、rubric 和谱系，再重跑受影响验证。

验证记录包含实际命令、Harbor/镜像/评分器版本、任务哈希、trial/job 标识、reward、日志、耗时与清理结果。每项状态为 passed/failed/not_run；未运行项不填执行时间。参考解与空输出验证通过说明运行和评分闭环有效，独立模型 rollout 的能力表现另行记录。仅有静态 review 的任务继续为草案。

## 构造方法与模板

环境、参考解、评分器与批量验收分别见 [环境构造](environment-construction.md)、[参考解](reference-solution.md)、[评分器](scorer-construction.md)、[批量生产](batch-production.md)。assets 中的 shell 模板规定接口，需要作者在包内实现 build_reference.py/grade.py；模板本身不是完整参考解或评分器。运行 `python scripts/validate_task_package.py <task目录> --require-harbor` 做静态检查，再按验证方法执行实际运行。
