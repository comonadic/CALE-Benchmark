#!/usr/bin/env bash
set -euo pipefail
rm -f /logs/verifier/reward.json /logs/verifier/report.json
mkdir -p /logs/verifier
python3 /tests/grade.py
