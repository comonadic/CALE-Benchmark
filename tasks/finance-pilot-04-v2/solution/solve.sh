#!/bin/bash
set -euo pipefail
solution_dir="$(cd "$(dirname "$0")" && pwd)"
output_dir="${OUTPUT_DIR:-/workspace/output}"
mkdir -p "$output_dir"
cp "$solution_dir/reference/risk_ledger.csv" "$output_dir/risk_ledger.csv"
cp "$solution_dir/reference/funding_results.json" "$output_dir/funding_results.json"
cp "$solution_dir/reference/action_memo.md" "$output_dir/action_memo.md"
