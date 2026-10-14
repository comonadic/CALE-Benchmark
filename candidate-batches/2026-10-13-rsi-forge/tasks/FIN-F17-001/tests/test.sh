#!/usr/bin/env bash
set -euo pipefail
mkdir -p /logs/verifier
rm -f /logs/verifier/reward.json /logs/verifier/report.json
python /tests/grade.py
