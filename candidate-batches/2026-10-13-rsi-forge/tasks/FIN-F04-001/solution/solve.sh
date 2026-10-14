#!/usr/bin/env bash
set -euo pipefail
rm -rf /workspace/output/*
python3 /workspace/solution/build_reference.py
