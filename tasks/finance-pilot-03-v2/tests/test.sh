#!/bin/bash
set -uo pipefail
TASK_LOG_DIR="${VERIFIER_LOG_DIR:-/logs/verifier}"
TASK_INPUT_DIR="${TASK_INPUT_DIR:-/workspace/input-data}"
TASK_OUTPUT_DIR="${TASK_OUTPUT_DIR:-/workspace/output}"
export TASK_INPUT_DIR
mkdir -p "$TASK_LOG_DIR"
rm -f "$TASK_LOG_DIR/reward.txt" "$TASK_LOG_DIR/reward.json" "$TASK_LOG_DIR/report.json"
TASK_TEST_DIR="$(cd "$(dirname "$0")" && pwd)"
if ! python "$TASK_TEST_DIR/runtime_guard.py" --input-dir "$TASK_INPUT_DIR" --log-dir "$TASK_LOG_DIR"; then
  rm -f "$TASK_LOG_DIR/reward.txt" "$TASK_LOG_DIR/reward.json"
  if [ ! -f "$TASK_LOG_DIR/report.json" ]; then
    printf '{"status":"invalid","verifier_failed":true,"grading_complete":false,"error":"Trusted runtime preflight could not execute"}\n' > "$TASK_LOG_DIR/report.json"
  fi
  exit 2
fi
if [ ! -s "$TASK_OUTPUT_DIR/distribution-model.xlsx" ] || [ ! -s "$TASK_OUTPUT_DIR/distribution-note.docx" ]; then
  printf '0\n' > "$TASK_LOG_DIR/reward.txt"
  printf '{"reward":0}\n' > "$TASK_LOG_DIR/reward.json"
  printf '{"status":"completed","valid":true,"submission_status":"invalid_submission","grading_complete":true,"reward":0,"professional_points":null,"candidate_failure_reason":"required deliverable missing or empty"}\n' > "$TASK_LOG_DIR/report.json"
  exit 0
fi
python "$TASK_TEST_DIR/candidate_guard.py" --output-dir "$TASK_OUTPUT_DIR" --log-dir "$TASK_LOG_DIR"
candidate_status=$?
if [ "$candidate_status" -eq 3 ]; then
  exit 0
fi
if [ "$candidate_status" -ne 0 ]; then
  rm -f "$TASK_LOG_DIR/reward.txt" "$TASK_LOG_DIR/reward.json"
  printf '{"status":"invalid","verifier_failed":true,"grading_complete":false,"error":"Native candidate readability checker failed unexpectedly"}\n' > "$TASK_LOG_DIR/report.json"
  exit 2
fi
python "$TASK_TEST_DIR/verify.py" --output-dir "$TASK_OUTPUT_DIR" --log-dir "$TASK_LOG_DIR"
status=$?
if [ -f "$TASK_OUTPUT_DIR/distribution-model.xlsx" ] && [ -f "$TASK_OUTPUT_DIR/distribution-note.docx" ]; then
  rm -f "$TASK_LOG_DIR/reward.txt" "$TASK_LOG_DIR/reward.json"
  python "$TASK_TEST_DIR/rubric_bridge.py" --output-dir "$TASK_OUTPUT_DIR" --log-dir "$TASK_LOG_DIR"
  status=$?
fi
exit "$status"
