#!/usr/bin/env bash
set -euo pipefail
mkdir -p /workspace/output
cp /solution/reference/rectification-ledger.csv /workspace/output/rectification-ledger.csv
python /solution/build_memo.py --output /workspace/output/review-memo.docx
