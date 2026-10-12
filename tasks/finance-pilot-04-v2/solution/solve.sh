#!/bin/bash
# Reference solution: derive the deliverables from the visible inputs.
#
# This does not copy pre-built bytes. Every number is recomputed from
# input-data/ and the attached rule versions by build_reference.py, which is
# what makes the oracle evidence that the task is solvable from what the agent
# can actually see.
set -euo pipefail

solution_dir="$(cd "$(dirname "$0")" && pwd)"
input_dir="${INPUT_DIR:-/workspace/input-data}"
output_dir="${OUTPUT_DIR:-/workspace/output}"

mkdir -p "$output_dir"

python3 "$solution_dir/build_reference.py" \
    --input-data "$input_dir" \
    --output "$output_dir"

# The memo and ledger carry professional prose that the builder reproduces from
# the same inputs; assert they were actually produced rather than assumed.
for artifact in funding_results.json risk_ledger.csv action_memo.md; do
    if [ ! -s "$output_dir/$artifact" ]; then
        echo "reference build did not produce $artifact" >&2
        exit 1
    fi
done
