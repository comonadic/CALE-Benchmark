# 工作流调研与任务类型卡

可单独使用，与资源库采集、抽取并列，属于造题前的准备工作。产物是可不断追加的**任务类型库**；造题时从库里取卡，再按卡从资源库选 input-data。本步骤不出题、不写 instruction。

## 目的

让题目来自真实存在的法律工作，而不是从材料倒推出来的场景。一张卡回答：谁在什么程序节点做这件事、用什么软件、做完交什么、行业自己怎么判断做对了、需要哪些输入。

## 在哪里找

| 来源 | 主要用来确认什么 | 例子 |
|---|---|---|
| 从业者讨论与经验文章 | 任务存在、实际步骤、常见坑、用什么软件 | 知乎、无讼、iCourt、律所公众号转载、法务社群文章 |
| 岗位说明与招聘 JD | 任务归属的岗位、频次、工作量 | 律师助理、非诉/诉讼律师、企业法务、合规岗 JD |
| 执业规范与业务操作指引 | 理想产物的形态与复核要点 | 律协业务操作指引、证券法律业务执业规则、尽调清单、合同审查清单 |
| 法考与执业培训材料 | 所需专业能力、难度层次 | 法考大纲、实习律师培训、律协课程 |
| 公开产物样本 | 产物真实长什么样 | 法律意见书、问询回复、裁判文书、仲裁裁决公开版 |
| 软件文档与教程 | 专业软件在该工作中的真实用法 | Word 修订与比对、法规库检索、案件管理系统手册 |

证据只存 URL、定位和短摘录，不批量搬运原文；涉及当事人和个人信息的内容不入库。

## 一张卡何时算成立

- **真实**：至少两条独立来源印证同一工作（例如一篇从业者文章加一份操作指引或 JD）。只有单一来源时标 `candidate`。
- **长程**：从业者完成需要数十分钟以上、多个步骤、多份材料之间的往返，而不是一次检索。
- **可验证**：整体任务能被判定做得对不对。看的是产物中有足够多可客观核对的部分（条款定位、冲突识别、要件对应、期间与金额计算、法源版本、修订位置），能区分做好和做差；论证与策略部分以证据约束的 rubric 评估，不要求唯一结论。
- **专业软件真实参与**：卡上的软件是这项工作在真实工作流里会使用的，例如 Word 修订、法规库检索、PDF 标注；装进容器或通过 MCP/CUA 提供。批量取数环节不进入任务，所需案卷与规范由 input-data 以对应时点版本提供。

## 卡片格式

模板见 [任务类型卡](../assets/task-card.template.yaml)。每张一个 YAML 文件，存放在 `task-library/legal/<工作族>/<task_type_id>.yaml`。字段要点：

- `trigger`：工作在什么程序或交易节点、因为什么发生。这是判断"真不真"最直接的字段。
- `workflow_steps`：从业者实际的动作序列，按来源整理，不按作者想象补全。至少 3 步。
- `software`：工作中使用的专业软件及用途；`provision` 必须是 `container`、`mcp`、`cua` 或 `input-data` 之一。桌面软件（Word/Excel）通常用 `cua`；可装包的命令行工具用 `container`；外部 API 用 `mcp`；只提供数据快照时用 `input-data`。
- `deliverables`：理想产物的文件与形态。文件名用相对路径，不含 `..`。
- `verification`：行业自己的复核要点，分三部分：`profession_checks`（业务规范）、`objective_parts`（可客观核对的部分）、`rubric_parts`（需要判断评估的部分）。三部分都必须有内容。
- `input_data`：需要的材料种类、时点（事项发生时有效的规范版本）、来源提示（写 `S01` 等 S 编号，编号须存在于 [来源索引](sources.md)）。
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

- 诉讼：证据梳理 → 争点与要件对应矩阵 → 请求金额计算 → 起诉状或代理意见
- 并购：公开披露核对 → 授权与决议链条审查 → 交割条件清单 → 尽调报告章节
- 破产：债权申报审查 → 担保与顺位认定 → 清偿测算 → 债权表异议意见

融合条件：前一步的产物是后一步的真实输入，且共用同一批 input-data。不相关的任务拼在一起不算融合，只是把题变长。卡片的 `fusable_with` 记录已确认的上下游关系，造题时沿这条链组合。

## 维护

- `task_type_id` 用 `LAW-<工作族编号>-<序号>`，如 `LAW-L02-004`，追加不复用。
- 去重轴：工作族 × 触发节点 × 主要产物。三者都相同的卡合并，来源追加到 `evidence`。
- `status`：`candidate`（来源不足）→ `verified`（满足四条成立条件）→ `instantiated`（已用于造题，记录题目 ID）。
- 题目试跑后发现的问题（例如可验证部分太少、软件未被真正使用）回写到卡片 `notes`。
