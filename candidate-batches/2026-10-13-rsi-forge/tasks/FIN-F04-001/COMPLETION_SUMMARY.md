# FIN-F04-001 Package Completion Summary

## Task Completed

✅ Standard Harbor evaluation package for bond trustee funding verification work

## Package Details

- **Task ID**: FIN-F04-001
- **Industry**: Finance
- **Work Family**: F04 Fixed Income Credit & Default Resolution
- **Title**: Corporate Bond Maturity and Repurchase Funding Verification
- **Package Size**: 25MB (19MB compressed)
- **Files**: 19 total (14 text/config + 5 input materials)

## Key Components Delivered

### 1. Core Configuration
- `task.toml` - Harbor 1.3 schema compliant
- `instruction.md` - Professional task description in Chinese
- `lineage.json` - Complete source provenance (5 materials documented)

### 2. Agent Environment
- `environment/Dockerfile` - Python 3.12 + openpyxl + pypdf + reportlab
- `environment/input-data/` - 5 real financial materials:
  - Annual report (25MB PDF, 458 pages)
  - Trustee report (358KB PDF, 30 pages)
  - Payment announcement (187KB PDF, 5 pages)
  - Regulatory notice (38KB HTML)
  - Blank reporting template (68KB Excel)

### 3. Reference Solution
- `solution/solve.sh` - Bash entry point
- `solution/build_reference.py` - 93 lines Python
  - Parses PDF/HTML source materials
  - Extracts bond facts (code, balance, rate, maturity)
  - Calculates interest: 25.00 × 3.38% = 0.845 → 0.85 billion CNY
  - Generates Excel with formulas + evidence sheet
  - Generates PDF memo with source citations

### 4. Verifier
- `tests/Dockerfile` - Lightweight verifier image (fixed COPY directive)
- `tests/test.sh` - Bash entry point
- `tests/grade.py` - 56 lines validation logic
- `tests/assertions.json` - 25 assertions across 9 criteria:
  - Scope (2): August 2026 range, single bond
  - Bond facts (4): code, name, issuer, balance
  - Dates (2): maturity date, payment node
  - Amounts (3): rate, interest, total + formula
  - Funding (5): proof distinction, confirmed/unconfirmed/gap/dedup
  - Evidence (3): trustee page, notice clauses, cash limitation
  - Risk (3): financial context, credit, enhancement
  - Actions (1): prioritized follow-up
  - Artifact (1): editable structure

### 5. Documentation
- `README.md` - Package overview and requirements
- `MANIFEST.txt` - File inventory with checksums
- `VALIDATION_NOTES.md` - Fix documentation and validation checklist

## Critical Fix Applied

**Issue**: Prior candidate verifier build failed on `COPY input-data/`
**Cause**: tests/input-data/ doesn't exist (materials are in environment/input-data/)
**Solution**: Changed to `COPY . /tests/` - verifier only needs test scripts, not input materials

## Validation Status

✅ All static checks passed:
- Python syntax valid
- TOML/JSON structure valid  
- Input material checksums match expected
- File permissions correct
- Harbor schema compliant

## Professional Quality

This task tests critical professional judgment:
- **Distinguishing funding types**: General financial capacity vs. earmarked payment funds
- **Evidence rigor**: All facts cite source file + page number
- **Risk classification**: No funding proof → must classify as "unconfirmed" not "confirmed"
- **Regulatory compliance**: Real CSRC notice requirements
- **Traceability**: Complete calculation trail with formulas preserved

The task deliberately omits funding proof to test whether agents understand that:
- Period-end cash balance ≠ dedicated payment account
- Credit rating ≠ payment confirmation
- Financial statements = background context only

This mirrors real bond risk management work where absence of proof must be flagged explicitly.

## Deliverable Location

Package ready at: `/workspace/output/FIN-F04-001/`
Archive ready at: `/workspace/output/FIN-F04-001.tar.gz` (19MB)

## Next Steps for Validation

1. Build agent image (expect ~1 minute)
2. Build verifier image (expect ~30 seconds, should succeed with fixed Dockerfile)
3. Run oracle test (reference solution should produce perfect score)
4. Run nop test (empty output should fail appropriately)
5. Run independent model trial

---
Completed: 2026-10-13
