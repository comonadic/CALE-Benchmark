#!/bin/bash
set -euo pipefail
test_dir="$(cd "$(dirname "$0")" && pwd)"
log_dir="${VERIFIER_LOG_DIR:-/logs/verifier}"
output_dir="${OUTPUT_DIR:-/workspace/output}"
mkdir -p "$log_dir"
rm -f "$log_dir/reward.txt" "$log_dir/reward.json" "$log_dir/judge-request.json" "$log_dir/judge-response.json"
printf '{"status":"verifier-invalid","valid":false,"verifier_failed":true,"task_id":"finance-pilot-04-v2","error_type":"EntryPointFailure","error":"verifier did not complete","reward_emitted":false}\n' > "$log_dir/report.json"
trap 'code=$?; if [ "$code" -ne 0 ]; then rm -f "$log_dir/reward.txt" "$log_dir/reward.json"; fi' EXIT
"${PYTHON_BIN:-python3}" "$test_dir/verifier.py" --output-dir "$output_dir" --log-dir "$log_dir" --judge-timeout "${JUDGE_TIMEOUT_SECONDS:-1800}"
