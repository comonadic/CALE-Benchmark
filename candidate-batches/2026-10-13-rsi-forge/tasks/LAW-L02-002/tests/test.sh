#!/usr/bin/env bash
set -euo pipefail
mkdir -p /logs/verifier
rm -f /logs/verifier/reward.txt /logs/verifier/reward.json /logs/verifier/report.json
trap 'code=$?; if [ "$code" -ne 0 ]; then rm -f /logs/verifier/reward.txt /logs/verifier/reward.json; fi' EXIT
python /tests/grade.py --input-data /workspace/input-data --output /workspace/output --logs /logs/verifier
