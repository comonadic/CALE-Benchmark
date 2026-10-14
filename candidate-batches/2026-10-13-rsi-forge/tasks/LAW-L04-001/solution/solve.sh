#!/usr/bin/env bash
set -euo pipefail
solution_dir="$(cd "$(dirname "$0")" && pwd)"
mkdir -p /workspace/output
python "$solution_dir/build_reference.py" --input-data /workspace/input-data --output /workspace/output
if command -v libreoffice >/dev/null 2>&1; then
  mkdir -p /tmp/lo-profile
  libreoffice -env:UserInstallation=file:///tmp/lo-profile --headless --convert-to xlsx --outdir /tmp /workspace/output/claim_calculation.xlsx >/dev/null 2>&1 || true
  if [ -s /tmp/claim_calculation.xlsx ]; then mv /tmp/claim_calculation.xlsx /workspace/output/claim_calculation.xlsx; fi
fi
