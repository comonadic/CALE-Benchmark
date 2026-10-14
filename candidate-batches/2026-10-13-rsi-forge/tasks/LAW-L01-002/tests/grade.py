#!/usr/bin/env python3
import argparse, json, re, sys, zipfile
from pathlib import Path
from lxml import etree
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def doc_text(path):
    with zipfile.ZipFile(path) as z:
        root = etree.fromstring(z.read("word/document.xml"))
        text = "".join(root.xpath(".//w:t/text() | .//w:delText/text()", namespaces=NS))
        return root, text, set(z.namelist())


def opinion_text(path):
    _, text, _ = doc_text(path)
    return text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-data", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--logs", required=True)
    args = ap.parse_args()
    out = Path(args.output); logs = Path(args.logs); logs.mkdir(parents=True, exist_ok=True)
    spec = json.loads((Path(__file__).parent / "assertions.json").read_text(encoding="utf-8"))
    red = out / "contract_redline.docx"; clean = out / "contract_clean.docx"; opinion = out / "review_opinion.docx"
    vals = {}
    errors = []
    try:
        # Missing candidate artifacts are ordinary candidate defects; malformed
        # artifacts are verifier failures because the submitted bytes cannot be inspected.
        if all(p.is_file() for p in (red, clean, opinion)):
            rr, rt, rn = doc_text(red)
            cr, ct, cn = doc_text(clean)
            ot = opinion_text(opinion)
            vals.update({"red": (rr, rt, rn), "clean": (cr, ct, cn), "opinion": ot})
    except Exception as exc:
        errors.append("verifier_failure: unreadable output: " + repr(exc))
    def exists_readable(p):
        return p.is_file() and p.stat().st_size > 1000
    redroot, redtext, rednames = vals.get("red", (None, "", set()))
    cleanroot, cleantext, cleannames = vals.get("clean", (None, "", set()))
    ot = vals.get("opinion", "")
    checks = {
      "redline_exists": exists_readable(red), "clean_exists": exists_readable(clean), "opinion_exists": exists_readable(opinion),
      "redline_ins": redroot is not None and bool(redroot.findall('.//' + W + 'ins')),
      "redline_del": redroot is not None and bool(redroot.findall('.//' + W + 'del')),
      "redline_comments": redroot is not None and 'word/comments.xml' in rednames and bool(redroot.findall('.//' + W + 'commentReference')),
      "project_number": "CZ2026-0463" in cleantext and "CZ2026-xxxx" not in cleantext,
      "payment_five": "5个工作日" in cleantext,
      "payment_source": "P270" in ot and ("优先" in ot or "不一致" in ot),
      "subcontracting": "不得违法转包" in cleantext and "采购需求" in cleantext,
      "sme_share": "40%" in ot and "28%" in ot,
      "preliminary_acceptance": "初步验收" in cleantext and "9个月" in cleantext,
      "prelim_seven_days": "7日" in cleantext,
      "final_acceptance": "合同验收" in cleantext and "12个月" in cleantext,
      "acceptance_ten_days": "10个工作日" in cleantext,
      "chapter_seven": "七、考核与验收" in cleantext,
      "typo_fixed": "巡检、维修、保养" in cleantext and "s维修" not in cleantext,
      "amount_not_invented": "中标总价" in ot and "不得以预算金额" in ot,
      "party_not_invented": "乙方名称" in ot and "授权签约代表" in ot,
      "staged_payment": "30%/30%/20%/20%" in ot,
      "confidentiality": "保密协议" in ot and "项目团队" in ot,
      "performance_scheme": "附件1绩效考核方案" in ot,
      "legal_business_split": "法律底线" in ot and "商业决定" in ot,
      "source_basis": "P210" in ot and "P270-P282" in ot,
      "clean_no_markup": cleanroot is not None and not cleanroot.findall('.//' + W + 'ins') and not cleanroot.findall('.//' + W + 'del')
    }
    results=[]
    for a in spec["assertions"]:
        passed = bool(checks.get(a["id"], False))
        results.append({"id":a["id"], "status":"passed" if passed else "failed", "actual":passed, "expected":True, "unit":a["unit"]})
    passed_count = sum(r["status"] == "passed" for r in results)
    caps = [float(e["cap"]) for e in spec.get("critical_errors", []) if next((r for r in results if r["id"] == e["assertion"]), {}).get("status") == "failed"]
    reward = min(1.0, passed_count / int(spec["scale"]))
    if caps: reward = min(reward, min(caps))
    status = "verifier_failure" if errors else ("graded" if passed_count == int(spec["scale"]) else "graded_candidate_defect")
    report = {"status":status, "valid":not bool(errors), "P":passed_count, "S":int(spec["scale"]), "reward":reward, "assertions":results, "errors":errors}
    (logs / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (logs / "reward.json").write_text(json.dumps({"reward":0 if errors else reward}), encoding="utf-8")
    if errors: return 2
    return 0 if passed_count == int(spec["scale"]) else 1

if __name__ == "__main__": sys.exit(main())
