# 工作流调研与任务类型卡

可单独使用，与资源库采集、抽取并列，属于造题前的准备工作。产物是可不断追加的**任务类型库**；造题时从库里取卡，再按卡从资源库选 input-data。本步骤不出题、不写 instruction。

## 目的

让题目来自真实存在的工作，而不是从材料倒推出来的场景。一张卡回答：谁在什么节点做这件事、用什么软件、做完交什么、行业自己怎么判断做对了、需要哪些输入。

## 在哪里找

| 来源 | 主要用来确认什么 | 例子 |
|---|---|---|
| 从业者讨论与经验文章 | 任务存在、实际步骤、常见坑、用什么软件 | 知乎、经管之家、雪球、公众号转载、券商/律所/会计所的培训文章 |
| 岗位说明与招聘 JD | 任务归属的岗位、频次、工作量 | 分析师、风控、审计、财资等岗位 JD |
| 执业规范、监管指引、内部操作手册公开版 | 理想产物的形态与复核要点 | 底稿指引、审计准则、评级方法、交易所业务规则 |
| 资格考试与培训大纲 | 所需专业能力、难度层次 | CPA、CFA、FRM、证券/基金从业 |
| 公开产物样本 | 产物真实长什么样 | 研报、评级报告、审计报告、问询回复、受托报告 |
| 软件文档与教程 | 专业软件在该工作中的真实用法 | Excel 建模教程、财务/风控系统手册、终端插件文档 |

证据只存 URL、定位和短摘录，不批量搬运原文；涉及个人信息的帖子不入库。

## 一张卡何时算成立

- **真实**：至少两条独立来源印证同一工作（例如一篇从业者文章加一份规范或 JD）。只有单一来源时标 `candidate`。
- **长程**：从业者完成需要数十分钟以上、多个步骤、多份材料之间的往返，而不是一次查找。
- **可验证**：整体任务能被判定做得对不对。看的是产物中有足够多可客观核对的部分（数值、勾稽、条款定位、台账字段、状态判断），能区分做好和做差；不要求每一部分都可机械判定，判断性部分以证据约束的 rubric 评估。
- **专业软件真实参与**：卡上的软件是这项工作在真实工作流里会打开、编辑、重算或导出的；装进容器或通过 MCP/CUA 提供。数据终端的取数环节不进入任务，所需数据由 input-data 以对应时点快照提供。

## 卡片格式

模板见 [任务类型卡](../assets/task-card.template.yaml)。每张一个 YAML 文件，存放在 `task-library/finance/<工作族>/<task_type_id>.yaml`。字段要点：

- `trigger`：工作在什么节点、因为什么发生。这是判断"真不真"最直接的字段。
- `workflow_steps`：从业者实际的动作序列，按来源整理，不按作者想象补全。至少 3 步。
- `software`：工作中使用的专业软件及用途；`provision` 必须是 `container`、`mcp`、`cua` 或 `input-data` 之一。桌面软件（Excel/Word）通常用 `cua`；可装包的命令行工具用 `container`；外部 API 用 `mcp`；只提供数据快照时用 `input-data`。
- `deliverables`：理想产物的文件与形态。文件名用相对路径，不含 `..`。
- `verification`：行业自己的复核要点，分三部分：`profession_checks`（业务规范）、`objective_parts`（可客观核对的部分）、`rubric_parts`（需要判断评估的部分）。三部分都必须有内容。
- `input_data`：需要的材料种类、时点、来源提示（写 `S01` 等 S 编号，编号须存在于 [来源索引](sources.md)）。
- `fusable_with`：已确认上下游关系的其他卡（含 `id`/`relation`/`note` 三个字段）；引用的 id 必须是库里已存在的卡。不确定时保持空列表。
- `evidence`：来源记录，见下方格式要求。
- `notes`：对卡片边界、来源局限或待补事项的说明。不能为空字符串。

### evidence 字段格式

每条来源记录必须包含以下所有字段，校验器会逐字段检查：

```yaml
evidence:
  - id: WF-YYYYMMDD-NN           # 全库唯一，格式 WF-<日期>-<序号>
    type: practitioner | regulation | guideline | training | software_documentation | public_artifact | operating_procedure
    origin: 原始作者或机构名称     # 转载不计为新来源，按原作者归属
    url: https://...              # 必须是完整 HTTP(S) 地址
    locator: 文档内的定位描述      # 章节/条款/页码/段落
    excerpt: 关键内容摘要          # 50-200 字，说明该来源印证了卡片的哪些事实
    supports:                     # 列出该来源实际覆盖的字段，从下方集合中选
      - role                      # 可选项：role | trigger | workflow_steps |
      - workflow_steps             #   deliverables | verification | software
      - software
    checked_at: 'YYYY-MM-DD'     # ISO 日期，实际读取原文的日期
    access: full_text | full_text_official_republication | full_text_attributed_republication | indexed_excerpt_only
```

**`verified` 状态的最低证据要求**（校验器强制检查）：
1. 至少两条来自不同原始机构/作者的来源，均有 `access` 为 `full_text*`，且 `supports` 包含 `workflow_steps`。
2. 至少一条来源有 `access` 为 `full_text*`，且 `supports` 包含 `software`。
3. `software` 列表中至少一项的 `provision` 是 `container`、`mcp` 或 `cua`（而非 `input-data`）。

转载、镜像和官方转载只计为原始来源的一次引用，不作独立来源计数。

## 关联任务融合

难度主要通过把**真实工作流里本就相连**的任务合成一道题获得，例如：

- 信用：财报口径重建 → 债务与担保去重 → 现金压力情景 → 授信审查意见
- 衍生品：规则版本确认 → 保证金重算 → 交易计划合规审查 → 风险台账
- 审计/投行：跨文件核对 → 差异台账 → 调整计算 → 问询回复

融合条件：前一步的产物是后一步的真实输入，且共用同一批 input-data。不相关的任务拼在一起不算融合，只是把题变长。卡片的 `fusable_with` 记录已确认的上下游关系，造题时沿这条链组合。

## 维护

- `task_type_id` 用 `FIN-<工作族编号>-<序号>`，如 `FIN-F13-003`，追加不复用。
- 去重轴：工作族 × 触发节点 × 主要产物。三者都相同的卡合并，来源追加到 `evidence`。
- `status`：`candidate`（来源不足）→ `verified`（满足四条成立条件）→ `instantiated`（已用于造题，记录题目 ID）。
- 题目试跑后发现的问题（例如可验证部分太少、软件未被真正使用）回写到卡片 `notes`。
