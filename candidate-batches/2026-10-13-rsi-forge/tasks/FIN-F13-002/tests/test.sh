#!/bin/bash
set -euo pipefail
exec python /tests/grade.py --input-data /workspace/input-data --output /workspace/output --logs /logs/verifier
