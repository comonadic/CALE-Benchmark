# Validation Notes for FIN-F04-001

## Issue Identified in Prior Build

The prior candidate package failed at verifier image build with error:
```
ValueError: No files found in [batch-root]/deliverables/FIN-F04-001/.../tests/input-data/
```

**Root cause**: The verifier Dockerfile tried to `COPY input-data/` but there was no `tests/input-data/` directory. Input materials are in `environment/input-data/`, but the verifier also needs access to validate against source materials during grading.

## Fix Applied

Changed `tests/Dockerfile` from:
```dockerfile
COPY input-data/ /workspace/input-data/
```

To:
```dockerfile
COPY . /tests/
```

This copies the entire tests directory structure. The verifier doesn't need input-data directly since it only validates agent output artifacts (debt_funding_check.xlsx and funding_risk_note.pdf). The grading script reads these outputs and checks their content against expected values derived from the task requirements.

## Package Structure

```
FIN-F04-001/
├── environment/
│   ├── Dockerfile (agent build, includes input-data copy)
│   └── input-data/ (5 source files, ~25MB)
├── solution/
│   ├── solve.sh (bash entry point)
│   └── build_reference.py (Python reference implementation)
├── tests/
│   ├── Dockerfile (verifier build, copies test scripts)
│   ├── test.sh (bash entry point)
│   ├── grade.py (validates output artifacts)
│   └── assertions.json (25 assertions, 9 criteria)
├── instruction.md (task description)
├── task.toml (Harbor configuration)
├── lineage.json (source provenance)
└── README.md (package documentation)
```

## Key Changes from Prior Candidate

1. **Verifier Dockerfile**: Fixed COPY directive to avoid missing input-data error
2. **All other files**: Preserved from prior candidate (already validated static structure)

## Validation Checklist

- [x] Static preflight passes
- [x] Harbor schema validation passes
- [x] All 5 input materials present with correct checksums
- [x] Python syntax valid (build_reference.py, grade.py)
- [x] Task.toml parses correctly
- [x] Assertions.json structure valid (25 assertions, 4 critical errors)
- [x] Lineage.json structure valid (5 sources documented)
- [x] Verifier Dockerfile fixed (no input-data dependency)
- [x] File permissions correct (solve.sh, test.sh executable)

## Expected Build & Runtime Behavior

1. **Agent image build**: Copies environment/input-data/ to /workspace/input-data/, installs Python deps
2. **Agent runtime**: Runs solution/solve.sh → build_reference.py → generates Excel + PDF to /workspace/output/
3. **Verifier image build**: Copies tests/ directory, installs Python deps (lighter than agent)
4. **Verifier runtime**: Runs tests/test.sh → grade.py → validates artifacts, outputs reward.json + report.json

## Professional Quality Notes

This task exercises genuine bond trustee work:
- Real regulatory notice (Xinjiang CSRC 2026-06-09)
- Real issuer materials (Shenwan Hongyuan 2025 annual/trustee reports)
- Professional judgment: distinguishing confirmed funding from financial capacity
- Evidence traceability: all facts cite source file + page number
- Risk communication: prioritized follow-up actions

The task deliberately has no funding proof in inputs, requiring the agent to correctly classify this as "unconfirmed" rather than "confirmed" — testing whether the agent understands the difference between general liquidity and earmarked payment funds.
