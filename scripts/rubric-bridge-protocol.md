# Offline-container rubric bridge protocol v1

The container performs objective checks and extracts the submitted files. It writes `/logs/verifier/judge-request.json` and waits for an independently produced `/logs/verifier/judge-response.json`. No grader credential or answer material is included in the agent image. Each candidate is reviewed from its actual output; there is no reference-answer hash whitelist or whole-answer/keyword matching.

Request JSON fields:

- `schema_version: 1`, `task_id`, `instruction`.
- `rubric: {criteria: [{id, points, ...professional requirements and acceptable alternatives...}]}`; stable IDs, total points explicit.
- `inputs`: complete extracted agent-visible materials keyed by filename; factual roles and version scope retained.
- `outputs`: complete extracted candidate files keyed by filename. XLSX includes actual values, formulas, caches and coordinates; DOCX distinguishes current text from deleted revision text.
- `objective`: objective findings, calculations and assertion results; `objective_returncode`, `extraction_errors`.
- `output_sha256`: actual submitted-file byte digests; `evidence_context` may contain a source index and judge-only verified facts.
- Optional `source_images: [{media_type: "image/png", data: "base64 PNG"}]` for source figures requiring visual review.
- `request_sha256`: SHA256 of UTF-8 JSON of all other request fields with `ensure_ascii=False, sort_keys=True, separators=(',', ':')`.

Response JSON:

- Same `request_sha256`, `judge_kind: "independent-model-rubric"` or `"independent-reviewer-rubric"`; `judge_identity` records the actual API model/protocol/response_id/usage, or the actual current-session reviewer ID and evidence-based review method.
- `criteria: [{id, score, reason, evidence: [candidate/input location or short quotation]}]`; each rubric ID exactly once, score between zero and that criterion's points. Positive credit requires concrete evidence. Scoring accepts substantively supported different wording, reasoning and business choices. Contradictions and source-role mistakes need substantive evaluation.

Container finalization validates the request binding, complete criterion coverage, score ranges and evidence. It writes report.json with assertions, criterion scores/reasons and the actual judge response, then reward.json with numerical reward `sum(score)/sum(points)`. It checks the trusted input snapshot's filenames, SHA256 digests and readability before assigning zero to empty required outputs. Missing or corrupt trusted inputs, unavailable parsing/native-engine dependencies, failed objective execution, or missing/malformed judge responses are verifier failures without a task reward. Corrupt candidate ZIP/XML or unreadable candidate deliverables are delivery defects: retain actual byte digests and failed objective checks, assign zero if no required deliverable is readable, and otherwise send the readable content and defects for criterion-level professional review.

The host helper only reads/writes containers running an explicitly listed verifier image ID, and requires permitted task ID prefixes. Local reviewer mode does not load credentials or invoke the external API. If an API route is explicitly authorized, credentials remain host-side and are loaded from the coordinator-approved env file. Exact output digests bind independently made assessments to actual trial bytes; they do not substitute for professional review. Network remains disabled inside containers, including Forge's Docker provider.

Example invocation (inside the global lifecycle lock held by the task runner):

```sh
DOCKER_CONFIG=/Users/czx/Documents/data/output/ale-harbor-validation/runtime/docker-client \
  /Users/czx/Documents/data/rsi-forge/.venv/bin/python \
  /Users/czx/Documents/data/ale-material-atlas/harbor-tasks/_shared/host_rubric_bridge.py \
  --host unix:///private/tmp/ale-harbor-colima/ale/docker.sock \
  --image sha256:VERIFIER_IMAGE_ID \
  --task-prefix legal-pilot- \
  --review-directory /Users/czx/Documents/data/output/ale-harbor-validation/law/review-queue \
  --logs /Users/czx/Documents/data/output/ale-harbor-validation/law/judge
```

Multiple `--image` and `--task-prefix` arguments are supported. The daemon lifecycle, Docker builds, whole Harbor/Forge attempt and cleanup use the coordinator's global `fcntl.flock` execution lock. The bridge never restarts/stops Docker or deletes resources. Logs preserve actual requests, model responses, criterion assessments and usage, without credentials.

Current authorization mode: external grading API is disabled by default. The local example above places each actual request at `requests/<container-id>.json`; after verifying the sealed output digests, it copies the native candidate and recalculated copies to `artifacts/<container-id>/`. An independent current-session reviewer reads the actual request, authoritative sources and native candidate, then writes `responses/<container-id>.json` with `judge_kind=independent-reviewer-rubric`, identity, matching request digest and complete evidence-backed criteria. Each candidate is assessed anew. Candidate case names, expected rewards, references and author scores remain outside that review queue. This is reviewer-assisted local validation, not an external API call or autonomous independent solver rollout.

An explicitly authorized external route instead requires `--allow-external-api`, `--model`, and `--env-file` (and optionally `--base-url`), with no `--review-directory`. The flag alone is not authorization. Source images are transmitted only in that separately authorized mode; local reviewers inspect the actual image bytes locally.

The external helper uses Anthropic SSE with adaptive thinking, low effort and a 16,000-token requested output budget. It preserves the raw events, complete response, reported usage and outgoing request metadata without credentials. A stream missing `message_stop`, truncated output or an invalid criterion response produces a `judge-error` envelope instead of scores. The verifier rejects that envelope immediately, records an infrastructure failure and lets the runner reclaim resources; it does not wait out the full reviewer timeout or fabricate a task reward.

## 重复评分的输入缓存

宿主通道支持 `--prompt-cache-ttl 5m` 或 `--prompt-cache-ttl 1h`，默认 `off` 用于一次性请求。启用后，将固定题面、rubric、公开材料及来源图像置于相同的前缀，在前缀末尾加入 Anthropic `cache_control`；候选输出、客观检查和 request hash 放在其后。两部分合起来仍是完整的当前请求，图片顺序保持一致。每个候选都重新评阅，缓存不会复用分数或评审上下文中的旧答案。

记录实际 `usage.input_tokens`、`cache_creation_input_tokens`、`cache_read_input_tokens` 和 TTL 明细；不同来源版本、rubric、system 或路由可能使缓存失效。缓存写入也有成本，因此一次性验收不必预热，重复批次应按同题固定材料分组，并按实际间隔选择 TTL。中转站的费率和路由以该站当前配置及实际账单为准；公开缓存倍率或写入成功都不能替代缓存读取命中的实测。没有返回用量时，记录为未知。

## 已完成响应的故障恢复

`--recover-model-response <log-directory>` 只用于模型已经完整响应、评分桥未完成发布的恢复。原始请求须逐字段相等，元数据中的 model/request hash 须相同，响应须有真实 identity/usage、`end_turn` 与完整 SSE 标记；所有 rubric 项、分数范围和正分证据仍逐一校验。严格的 JSON 数字字符串可规范化为等值数字，原始响应保留，并记录转换过程；分数缺失、布尔值、分数字串、非有限值与越界值均拒绝。

恢复不加载模型凭据，不发 HTTP 请求；新 trial 仍实际生成产物、执行客观核查、绑定整个请求并回收资源，原失败记录保留。identity 记录原始 response ID、原始文件哈希与 `new_model_call=false`。任何题面、输入、rubric、产物或客观证据改变都不能使用这份恢复记录。它是受信任本地验收的故障恢复通道，不是参考答案或一般评分缓存。
