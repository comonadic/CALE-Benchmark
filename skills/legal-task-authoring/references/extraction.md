# 法律材料的抽取与证据组织

可单独用于资料整理和 reference 库维护。先盘点给定原件与覆盖范围，再按实际用途抽取；没有造题需求时不必建立 rubric。造题时将下述证据文件归入 `private/evaluation/`，并与评分项连接。

## 文书角色先于内容摘要

将每个段落标为：当事人主张、抗辩、证据原文、裁判认定、裁判理由、裁判结果、规范文本或任务给定假设。保留同一事实的冲突陈述，用冲突 ID 关联，不能用摘要模型自动裁定谁说的是真的。

事实记录：`fact_id, subject, action, object, event_date, date_precision, role, disputed, document_id, locator, quote`。精确日期缺失时保留月份或区间，避免补成某一具体日。

证据记录：`evidence_id, fact_ids, origin, formed_at, available_at, offered_by, supports_or_rebuts, document_id, locator`。公开裁判中的证据描述与真实证据附件分别标明来源。

规范记录：`authority_id, title, issuing_body, document_number, jurisdiction, provision, promulgated_at, effective_from, effective_to, version_url, applicability_reason`。新旧版本交接与过渡规则需要独立条目。

## 争点与合同的两套索引

争议任务用 `issue_id → 要件 → 待证事实 → 支持证据 → 反证 → 适用规范 → 可接受结论`。事实不足时写缺口及其对结论的影响，不凭判决反向补证。

合同任务用 `obligation_id, actor, beneficiary, trigger, action, deadline, exception, remedy, clause_id, referenced_annex, precedence`。同时提取定义条款、引用条款、优先级和变更机制。

| 工作族 | 专项核对 |
|---|---|
| 合同/采购 | 主文、技术附件、报价与付款条件，澄清/补充协议的优先级 |
| 并购/公司 | 主体、控制链、授权、交割条件与披露时点 |
| 破产/执行 | 债权组、清偿顺序、表决分母、资产与计划版本 |
| 专利/商标 | 申请号、优先权、权利要求版本、引证及法律状态日期 |
| 劳动/行政 | 工资和年限、通知送达、期间计算、当时地方规则 |
| 数据/仲裁 | 活动或条款事实、法域、适用规则版本与程序阶段 |

## 原件与产物的定位

PDF 用物理页码加引文，DOCX 用标题、条款号和原句，表格用表/行/列，扫描件同时保留页图及 OCR。重复条款编号必须带文档 ID。

合同修订保留 before/after 与理由，记录受影响的交叉引用；不要依赖排版页码作为 DOCX 唯一定位。输出 `evidence.json`、`authorities.json`、`issues.json`、`obligations.json`，支撑评分和可追溯审阅。

## 解析层的入库核验

文本长度只用于发现异常，不作为完整度判定。按页或内容块检查解析覆盖，抽查原件与解析文本的字符、阅读顺序及表格关系；关键内容解析失败时更换解析器或使用 OCR，保留处理方式、原件哈希与定位。缺文本的封面、签章或空白页与缺失业务内容分别记录。

模板空栏是待设定变量，不自动补成真实交易事实。案例选编按原件登记，使用其中单案时另外记录案号或章节；集合中的案例重叠不能仅靠文件哈希排除。
