#!/bin/bash
set -euo pipefail
solution_dir="$(cd "$(dirname "$0")" && pwd)"
output_dir="${OUTPUT_DIR:-/workspace/output}"
mkdir -p "$output_dir"
cp "$solution_dir/reference/client_note_revised.docx" "$output_dir/client_note_revised.docx"
cp "$solution_dir/reference/correction_log.csv" "$output_dir/correction_log.csv"
