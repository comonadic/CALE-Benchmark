#!/usr/bin/env bash
set -euo pipefail
solution_dir="$(cd "$(dirname "$0")" && pwd)"
mkdir -p /workspace/output
python "$solution_dir/build_reference.py" --input-data /workspace/input-data --output /workspace/output
