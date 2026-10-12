# Verifier operation

`test.sh` reads the actual `/workspace/output`, executes `objective.py` against the verifier-stage trusted input copies and extracts every material and the three candidate artifacts. It writes a canonical SHA256 sealed request to `/logs/verifier/judge-request.json` and waits for a fresh host-side rubric assessment.

The request contains the actual candidate digests, complete source/working-material extracts, instruction, seven professional criteria, and every objective arithmetic assertion. It contains no reference answer. Criterion scores come from a real independent review and are capped by the arithmetic/structure ceilings described in `rubric.json`; a numerical pass alone never earns professional credit.

The current approved review channel is an independent Codex reviewer. The response must contain `judge_kind: independent-reviewer-rubric`, matching `request_sha256`, and `judge_identity` with actual `reviewer_id`, `reviewed_at` and `method`, plus each R1–R7 exactly once with score, substantive reason and candidate/input evidence. Root injects it into the controlled offline verifier container. The model-rubric protocol is supported structurally but external API use is not authorized for this authoring run. No API key is copied to or read by this package.

Missing or empty declared candidate artifacts, and invalid JSON syntax or UTF-8 encoding in candidate `funding_results.json`, deterministically receive a completed `graded-candidate-failure` with reward0 and a specific missing/malformed list. Trusted source/code checks run first. Extraction, I/O, script, trusted-source and judge faults leave a `verifier-invalid` report and **no reward file**, so Harbor treats evaluation as failed. Complete normal candidates retain the weighted partial rubric score. Stale reward/request/response files are removed before each run. Response digest and original candidate-byte digests are validated before a reward is emitted.

Actual challenge artifacts live in `challenges/{numeric-wrong,semantic-wrong,acceptable-alternative}/output`. Author-side objective tests have executed. Native Docker, independent semantic grading, Harbor/Forge attempts and cleanup are still `not_run` until the coordinating runner executes them. Use the coordinator lifecycle lock and independent verifier-image isolation; only the root runner manages Docker.

See the repository shared `harbor-tasks/_shared/rubric-bridge-protocol.md`. The `host_rubric_bridge.py` network helper is not invoked by this package or author.
