#!/bin/bash
set -euo pipefail
log_dir="${VERIFIER_LOG_DIR:-/logs/verifier}"
output_dir="${OUTPUT_DIR:-/workspace/output}"
test_dir="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$log_dir"
rm -f "$log_dir/reward.txt" "$log_dir/reward.json" "$log_dir/rewards.json"
rm -f "$log_dir/report.json"
# Harbor ignores exit status when a reward survives. Infrastructure failure must
# remove any reward; normal absent/malformed candidate artifacts can receive0.
trap 'code=$?; if [ "$code" -ne 0 ]; then rm -f "$log_dir/reward.txt" "$log_dir/reward.json" "$log_dir/rewards.json"; if [ ! -f "$log_dir/report.json" ]; then printf "{\"valid\":false,\"verifier_failed\":true,\"error\":\"verifier entry point failed\"}\n" > "$log_dir/report.json"; fi; fi' EXIT
python_cmd="${PYTHON_BIN:-python3}"
"$python_cmd" "$test_dir/rubric_bridge.py" --output-dir "$output_dir" --log-dir "$log_dir"
