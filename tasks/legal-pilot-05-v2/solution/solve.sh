#!/bin/bash
set -euo pipefail
mkdir -p /workspace/output
cp /solution/reference/evidence-ledger.csv /workspace/output/evidence-ledger.csv
cp /solution/reference/argument-comparison.csv /workspace/output/argument-comparison.csv
cp /solution/reference/team-review.md /workspace/output/team-review.md
