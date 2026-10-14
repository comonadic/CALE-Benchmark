#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "$0")" && pwd)"
mkdir -p /workspace/output
python "$script_dir/build_reference.py" --input-data /workspace/input-data --output /workspace/output
