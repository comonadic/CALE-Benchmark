#!/bin/bash
# Verifier entry point: objective assertion grading, no host bridge.
#
# Writes /logs/verifier/report.json always, and /logs/verifier/reward.json only
# when this run produced a complete valid score. A verifier-side fault must be
# distinguishable from a candidate scoring zero, so it clears any stale reward
# and exits non-zero without emitting one.
set -euo pipefail

test_dir="$(cd "$(dirname "$0")" && pwd)"
log_dir="${VERIFIER_LOG_DIR:-/logs/verifier}"
output_dir="${OUTPUT_DIR:-/workspace/output}"
mkdir -p "$log_dir"

# A stale reward must never mask this run's outcome.
rm -f "$log_dir/reward.json" "$log_dir/reward.txt" \
      "$log_dir/judge-request.json" "$log_dir/judge-response.json"

"${PYTHON_BIN:-python3}" "$test_dir/grade.py" \
    --output-dir "$output_dir" \
    --log-dir "$log_dir" \
    --tests-dir "$test_dir"
