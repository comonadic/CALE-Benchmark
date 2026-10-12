#!/bin/bash
set -euo pipefail
mkdir -p /logs/verifier
python3 /tests/verifier.py
