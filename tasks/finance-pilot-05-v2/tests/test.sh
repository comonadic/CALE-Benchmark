#!/usr/bin/env bash
set -euo pipefail
test_dir="$(cd "$(dirname "$0")" && pwd)"
log_dir="${VERIFIER_LOG_DIR:-/logs/verifier}"
mkdir -p "$log_dir"
rm -f "$log_dir/reward.txt" "$log_dir/reward.json"
printf '{"status":"verifier_failure","valid":false,"reward":null,"error":"Verifier entry did not complete"}\n' > "$log_dir/report.json"
trap 'code=$?; if [ "$code" -ne 0 ]; then rm -f "$log_dir/reward.txt" "$log_dir/reward.json"; fi' EXIT
"${PYTHON_BIN:-python}" "$test_dir/offline_verifier.py" --output "${OUTPUT_DIR:-/workspace/output}" --input-data "${TASK_INPUT_DIR:-/tests/input-data}" --logs "$log_dir" --wait-seconds "${RUBRIC_WAIT_SEC:-1800}"
