# 任务卡材料资源库

材料按已审阅任务卡的 `input_data` 采集、组包和记录缺口。首批基于 `21667a9fa26a16e5e2f214031f10e327f5420b10` 的11张活动卡，优先使用2025年下半年及2026年正式披露原件。

- [可筛选的 Excel 材料目录](../outputs/01a12ec5-33b0-73d0-b60b-e9ed1659461e/CALE任务卡材料库.xlsx)：卡片覆盖、材料目录、36项输入缺口。
- [本批采集记录](batches/2026-10-13-task-inputs/README.md)：实际数量、核验范围、版本与适用限制。
- [文件索引](batches/2026-10-13-task-inputs/catalog.jsonl)、[质量记录](batches/2026-10-13-task-inputs/quality.jsonl)、[输入覆盖](batches/2026-10-13-task-inputs/input-coverage.json)：可以按卡片、主体、时点和材料角色选材。
- [`packages/`](packages/)：9组材料的关联键、默认截止日、版本链、默认输入和隔离文件。

真实材料文件及解析层均随仓库保存，克隆后可以直接读取。38份原件在 `raw/<source_id>/<document_id>/original.*`，每份带 `source_manifest.json` 和SHA-256。另1份审计报告通过 `business-pages.pdf` 保存完整业务正文（原始页1-6），含身份证信息的证照附页7-10没有公开；完整来源原件留在本地，原件哈希和删页范围见 `publication_manifest.json`。解析、OCR在 `parsed/`，连接来源原件哈希。

[实际入库文件清单](batches/2026-10-13-task-inputs/repository-files.json)逐项记录39份文件的仓库路径、哈希及大小，`repository_file_path` 是可直接读取的文件路径。ICC规则仍只保留链接及版本信息。

`accepted_public_source` 表示公开原件来源、格式和记录通过核验；`accepted_with_issue` 要阅读具体问题。两者都不表示一项真实工作所需的内部输入已齐备。任务实例化前，按输入覆盖表补授权材料，按默认视图隔离事后结果，并核对再分发范围。

复核本批（无需事先重新下载原件）：

```bash
python scripts/validate_reference_library.py reference-library/batches/2026-10-13-task-inputs
```

重取明确列入计划的原件，可使用 `scripts/acquire_reference_materials.py`。该脚本采用标准HTTP公开下载，不处理账号、验证码或非公开卷宗；已有文件需匹配记录哈希。PDF、Excel检查依赖 `pypdf`、`openpyxl`。macOS扫描件可用 `scripts/ocr_reference_pages.swift` 辅助阅读，OCR的金额和条款不是评分金标准。
