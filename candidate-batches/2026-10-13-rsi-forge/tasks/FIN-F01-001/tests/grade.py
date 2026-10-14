#!/usr/bin/env python3
import argparse
import json
import math
import re
import subprocess
import tempfile
from pathlib import Path

from openpyxl import load_workbook
from pypdf import PdfReader

FACTS = {
    "HIST-01": ("2025 revenue", 128468230914.96),
    "HIST-02": ("2024 revenue", 114601056662.29),
    "HIST-03": ("2025 cost", 115193343614.54),
    "HIST-04": ("2025 net income", 4545393791.33),
    "HIST-05": ("2025 cash", 3202836313.58),
    "HIST-06": ("2025 receivables", 2978763231.09),
    "HIST-07": ("2025 inventory", 11371777008.15),
    "HIST-08": ("2025 payables", 5726047396.44),
    "HIST-09": ("2025 fixed assets", 17007956953.83),
    "HIST-10": ("2025 short debt", 1163647077.79),
    "HIST-11": ("2026H1 revenue", 64239967963.30),
    "HIST-12": ("2026H1 cost", 58236827704.54),
    "HIST-13": ("2026H1 net income", 1726556952.59),
    "HIST-14": ("2026H1 operating cash flow", 3923561511.73),
    "HIST-15": ("2026H1 cash movement", 136480536.53),
    "HIST-16": ("2026H1 cash ending", 3135056270.10),
    "HIST-17": ("2026H1 inventory", 13917906683.60),
    "HIST-18": ("2026H1 total assets", 55290906075.56),
    "HIST-19": ("2026H1 total liabilities", 30198088271.98),
    "HIST-20": ("2026H1 total equity", 25092817803.58),
    "HIST-21": ("2026H1 investing cash flow", -2993726149.88),
    "HIST-22": ("2026H1 financing cash flow", -724819016.92),
    "HIST-23": ("2026H1 AR", 5411032161.70),
    "HIST-24": ("2026H1 fixed assets", 16764113281.15),
    "HIST-25": ("2026H1 CIP", 870886016.42),
    "HIST-26": ("2026H1 short debt", 3601033153.61),
    "HIST-27": ("2026H1 long debt", 249637310.50),
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--logs", type=Path, required=True)
    args = parser.parse_args()
    contract = Path("/tests/assertions.json")
    if not contract.exists():
        contract = Path(__file__).with_name("assertions.json")
    results = []
    try:
        assertions = json.loads(contract.read_text())
        xlsx = args.output / "three_statement_model.xlsx"
        pdf = args.output / "model_update_notes.pdf"
        if not xlsx.is_file() or not pdf.is_file():
            raise FileNotFoundError("required output missing")
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "recalc"
            out.mkdir()
            profile = Path(td) / "profile"
            subprocess.run(["soffice", "--headless", f"-env:UserInstallation=file://{profile}", "--convert-to", "xlsx", "--outdir", str(out), str(xlsx)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            recalced = out / xlsx.name
            if not recalced.exists():
                raise RuntimeError("LibreOffice did not produce recalculated workbook")
            wbv = load_workbook(recalced, data_only=True)
            wbf = load_workbook(xlsx, data_only=False)
        histv, histf = wbv["历史数据"], wbf["历史数据"]
        bylabel = {str(histv.cell(r, 1).value): r for r in range(2, histv.max_row + 1)}
        for aid, (label, expected) in FACTS.items():
            row = bylabel.get(label)
            actual = histv.cell(row, 4).value if row else None
            results.append((aid, isinstance(actual, (int, float)) and abs(actual - expected) <= 1, actual, expected))
        checks = wbv["检查"]
        cv = {str(checks.cell(r, 1).value): checks.cell(r, 2).value for r in range(2, checks.max_row + 1)}
        for aid, key in [("MODEL-01", "2026H1现金滚动差额"), ("MODEL-02", "H2现金滚动差额"), ("MODEL-03", "H2资产负债差额"), ("MODEL-05", "借款滚动差额"), ("MODEL-06", "固定资产滚动差额"), ("MODEL-07", "权益滚动差额")]:
            val = cv.get(key)
            if aid == "MODEL-03":
                bs_formula = str(wbf["资产负债表"]["B13"].value or "")
                ok = isinstance(val, (int, float)) and bs_formula.startswith("=") and not re.search(r"平衡|plug", bs_formula, re.I)
            else:
                ok = isinstance(val, (int, float)) and abs(val) <= 1
            results.append((aid, ok, val, "diagnostic formula" if aid == "MODEL-03" else "absolute value <= 1 yuan"))
        sensitivity = cv.get("H2收入增速+1个百分点影响")
        results.append(("MODEL-04", isinstance(sensitivity, (int, float)) and sensitivity > 0, sensitivity, "positive revenue impact"))
        formulas = {"revenue": str(wbf["利润表"]["B2"].value or ""), "ar": str(wbf["营运资本"]["D2"].value or ""), "inventory": str(wbf["营运资本"]["D3"].value or ""), "payables": str(wbf["营运资本"]["D4"].value or "")}
        results.append(("MODEL-08", formulas["revenue"].startswith("="), formulas["revenue"], "formula-driven revenue"))
        results.append(("MODEL-09", all(formulas[key].startswith("=") for key in ("ar", "inventory", "payables")), formulas, "formula-driven working capital"))
        citations = " ".join(str(histv.cell(r, 6).value or "") for r in range(2, histv.max_row + 1))
        results.append(("MODEL-10", "2025 annual report p.97" in citations, citations, "2025 annual report p.97"))
        results.append(("MODEL-11", "2026 half-year report p.61" in citations, citations, "2026 half-year report p.61"))
        workbook_text = " ".join(str(c.value or "") for ws in wbf.worksheets for row in ws.iter_rows() for c in row)
        results.append(("MODEL-12", bool(re.search(r"分析者情景|分析者情景参数", workbook_text)) and "非公司预算/指引" in workbook_text, workbook_text[:500], "scenario nature disclosed"))
        pdf_text = " ".join(page.extract_text() or "" for page in PdfReader(str(pdf)).pages)
        results.append(("MODEL-13", all(term in pdf_text for term in ("既有模型", "批准预算", "期末现金")), pdf_text[:1000], "limitations and scenario result in PDF"))
        row_labels = [str(histv.cell(r, 3).value or "") for r in range(2, histv.max_row + 1)]
        row_citations = [str(histv.cell(r, 6).value or "") for r in range(2, histv.max_row + 1)]
        evidence_ok = all("合并口径" in str(histv.cell(r, 5).value or "") and "人民币元" in str(histv.cell(1, 4).value or "") and row_labels[i] and row_citations[i] for i, r in enumerate(range(2, histv.max_row + 1)))
        results.append(("MODEL-14", evidence_ok, {"period_rows": len(row_labels), "scope_unit_citations_present": evidence_ok}, "period, RMB unit, consolidated scope, citation"))
        required_sheets = {"历史数据", "情景假设", "营运资本", "固定资产与债务", "利润表", "现金流量表", "资产负债表", "检查", "说明"}
        results.append(("MODEL-15", required_sheets <= set(wbf.sheetnames), wbf.sheetnames, sorted(required_sheets)))
        numeric_assumptions = all(isinstance(wbf["情景假设"].cell(r, 2).value, (int, float)) for r in range(2, 13))
        results.append(("MODEL-16", numeric_assumptions and formulas["revenue"].startswith("="), numeric_assumptions, "numeric editable input cells and formulas"))
        results.append(("MODEL-17", "情景假设" in str(wbf["检查"]["B8"].value), wbf["检查"]["B8"].value, "sensitivity formula references editable assumption"))
        results.append(("MODEL-18", all(term in pdf_text for term in ("2025", "合并口径", "分析者情景", "模型限制", "期末现金")), pdf_text[:1000], "PDF scope, scenario, limitations, results"))
        formula_errors = [(ws.title, c.coordinate, c.value) for ws in wbv for row in ws.iter_rows() for c in row if isinstance(c.value, str) and c.value.startswith("#")]
        results.append(("MODEL-19", not formula_errors, formula_errors, "no spreadsheet formula errors"))
        row_labels = [str(histv.cell(r, 3).value or "") for r in range(2, histv.max_row + 1)]
        row_citations = [str(histv.cell(r, 6).value or "") for r in range(2, histv.max_row + 1)]
        evidence_ok = all("合并口径" in str(histv.cell(r, 5).value or "") and "人民币元" in str(histv.cell(1, 4).value or "") and row_labels[i] and row_citations[i] for i, r in enumerate(range(2, histv.max_row + 1)))
        results.append(("MODEL-14", evidence_ok, {"period_rows": len(row_labels), "scope_unit_citations_present": evidence_ok}, "period, RMB unit, consolidated scope, citation"))
        required_sheets = {"历史数据", "情景假设", "营运资本", "固定资产与债务", "利润表", "现金流量表", "资产负债表", "检查", "说明"}
        results.append(("MODEL-15", required_sheets <= set(wbf.sheetnames), wbf.sheetnames, sorted(required_sheets)))
        numeric_assumptions = all(isinstance(wbf["情景假设"].cell(r, 2).value, (int, float)) for r in range(2, 13))
        results.append(("MODEL-16", numeric_assumptions and formulas["revenue"].startswith("="), numeric_assumptions, "numeric editable input cells and formulas"))
        sensitivity_formula = str(wbf["检查"]["B8"].value or "")
        results.append(("MODEL-17", "情景假设" in sensitivity_formula and "B12" in sensitivity_formula, sensitivity_formula, "sensitivity formula references editable assumption"))
        results.append(("MODEL-18", all(term in pdf_text for term in ("2025", "合并口径", "分析者情景", "限制", "期末现金")), pdf_text[:1000], "PDF scope, scenario, limitations, results"))
        formula_errors = [(ws.title, c.coordinate, c.value) for ws in wbv for row in ws.iter_rows() for c in row if isinstance(c.value, str) and c.value.startswith("#")]
        results.append(("MODEL-19", not formula_errors, formula_errors, "no spreadsheet formula errors"))
        errors = [aid for aid, ok, _, _ in results if not ok]
        reward = sum(ok for _, ok, _, _ in results) / assertions["scale"]
        if not math.isfinite(reward) or assertions["scale"] != len(assertions["assertions"]) or len(results) != assertions["scale"]:
            raise ValueError("invalid assertion scale or evaluated result count")
        caps = [item["cap"] for item in assertions.get("critical_errors", []) if item["assertion"] in errors]
        if caps:
            reward = min(reward, *caps)
        report = {"valid": True, "status": "graded_candidate_defect" if errors else "graded", "reward": reward, "P": sum(ok for _, ok, _, _ in results), "S": assertions["scale"], "results": [{"id": aid, "status": "pass" if ok else "fail", "actual": actual, "expected": expected} for aid, ok, actual, expected in results], "failed_assertions": errors}
    except Exception as exc:
        report = {"valid": False, "status": "verifier_failure", "error": f"{type(exc).__name__}: {exc}"}
    args.logs.mkdir(parents=True, exist_ok=True)
    (args.logs / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    reward_path = args.logs / "reward.json"
    reward_path.unlink(missing_ok=True)
    if report.get("valid"):
        reward_path.write_text(json.dumps({"reward": report["reward"]}))


if __name__ == "__main__":
    main()
