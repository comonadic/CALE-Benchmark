#!/usr/bin/env bash
set -uo pipefail
test_dir="$(cd "$(dirname "$0")" && pwd)"
log_dir="${VERIFIER_LOG_DIR:-/logs/verifier}"
mkdir -p "$log_dir"
rm -f "$log_dir/reward.txt" "$log_dir/reward.json"
printf '{"status":"verifier_failure","valid":false,"reward":null,"error":"verifier did not finish"}\n' > "$log_dir/report.json"
trap 'code=$?; if [ "$code" -ne 0 ]; then rm -f "$log_dir/reward.txt" "$log_dir/reward.json"; fi' EXIT
"${PYTHON_BIN:-python}" "$test_dir/offline_verifier.py" --output "${OUTPUT_DIR:-/workspace/output}" --input-data "${TASK_INPUT_DIR:-/workspace/input-data}" --logs "$log_dir" --wait-seconds "${RUBRIC_WAIT_SEC:-1800}"
status=$?
if [ ! -f "$log_dir/report.json" ]; then
  printf '{"status":"verifier_failure","valid":false,"reward":null,"error":"verifier did not produce a report"}\n' > "$log_dir/report.json"
fi
# A rubric failure is a completed grade. An execution failure has no reward
# because Harbor0.17.1 reads reward artifacts, not this exit code, for validity.
exit "$status"
