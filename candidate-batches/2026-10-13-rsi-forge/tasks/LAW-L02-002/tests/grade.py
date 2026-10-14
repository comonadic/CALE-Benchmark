#!/usr/bin/env python3
import argparse
import hashlib
import json
import re
import sys
import traceback
from pathlib import Path

from openpyxl import load_workbook
from pypdf import PdfReader

ASSERTIONS_PATH = Path(__file__).with_name("assertions.json")
EXPECTED_CASES_PATH = Path(__file__).with_name("expected_cases.json")
EXPECTED_SHA256 = "682acdfa0d8a2a8334c0c910b5a8c7ef4ffa3a0d0c8e650d85d73132dd10f6d0"


def norm(s):
    return re.sub(r"\s+", "", str(s or "")).replace("（", "(").replace("）", ")")


def pdf_text(path):
    return "\n".join(p.extract_text() or "" for p in PdfReader(str(path)).pages)


def source_pdf(input_dir):
    files=list(Path(input_dir).glob("*.pdf"))
    if len(files)!=1:
        raise RuntimeError(f"Expected exactly one source PDF, found {len(files)}")
    return files[0]


def check_candidate(input_dir, output_dir):
    source = source_pdf(input_dir)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if digest != EXPECTED_SHA256:
        raise RuntimeError(f"trusted input hash mismatch: {digest}")
    assertions = json.loads(ASSERTIONS_PATH.read_text(encoding="utf-8"))["assertions"]
    values = {}
    wb_path=output_dir/"evidence_workbook.xlsx"
    cat_path=output_dir/"evidence_catalog.pdf"
    note_path=output_dir/"supplementation_note.pdf"
    wb=None
    candidate_errors=[]
    if wb_path.is_file():
        try:
            wb=load_workbook(wb_path,data_only=False,read_only=False)
        except Exception as exc:
            candidate_errors.append(f"evidence_workbook.xlsx: {type(exc).__name__}: {exc}")
    elif not wb_path.is_file():
        candidate_errors.append("evidence_workbook.xlsx missing")
    cat=""
    if cat_path.is_file():
        try:
            cat=pdf_text(cat_path)
        except Exception as exc:
            candidate_errors.append(f"evidence_catalog.pdf: {type(exc).__name__}: {exc}")
    elif not cat_path.is_file():
        candidate_errors.append("evidence_catalog.pdf missing")
    note=""
    if note_path.is_file():
        try:
            note=pdf_text(note_path)
        except Exception as exc:
            candidate_errors.append(f"supplementation_note.pdf: {type(exc).__name__}: {exc}")
    elif not note_path.is_file():
        candidate_errors.append("supplementation_note.pdf missing")
    sheets=set(wb.sheetnames) if wb else set()
    casews=wb["案件登记"] if wb and "案件登记" in sheets else None
    rows={}
    if casews:
        headers=[casews.cell(1,c).value for c in range(1,casews.max_column+1)]
        for row in casews.iter_rows(min_row=2,values_only=True):
            rec={h: row[i] for i,h in enumerate(headers) if h}
            if rec.get("内部整理码"):
                rows[str(rec["内部整理码"])]=rec
    all_txt=cat+"\n"+note
    tnorm=norm(all_txt)
    expected_cases=json.loads(EXPECTED_CASES_PATH.read_text(encoding="utf-8"))
    formula_ok=False
    total_ok=False
    if wb and "金额汇总" in sheets:
        sm=wb["金额汇总"]
        formulas=[str(sm.cell(r,2).value or "") for r in range(2,5)]
        formula_ok=all(f.startswith("=") and "案件登记" in f for f in formulas[:2])
    expected_codes=[f"ANN-20260822-{'N' if x['group']=='N' else 'P'}{x['number']:02d}" for x in expected_cases]
    ids_present=all(code in rows for code in expected_codes)
    page_ok=ids_present and all(str(r.get("公告页码") or "").strip() for r in rows.values())
    docket_ok=ids_present and all(norm(rows[f"ANN-20260822-{'N' if meta['group']=='N' else 'P'}{meta['number']:02d}"].get("案号（公告）"))==norm(meta['case_no']) for meta in expected_cases)
    amount_ok=ids_present and all(abs(float(rows[f"ANN-20260822-{'N' if meta['group']=='N' else 'P'}{meta['number']:02d}"].get("涉案金额（万元）") or 0)-meta['amount'])<0.005 for meta in expected_cases)
    identity_ok=ids_present and all(all(norm(rows[f"ANN-20260822-{'N' if m['group']=='N' else 'P'}{m['number']:02d}"].get(col))==norm(m[field]) for col,field in [("原告（公告）","plaintiff"),("被告（公告）","defendant"),("案由（公告）","cause"),("受理法院（公告）","court")]) for m in expected_cases)
    newtotal=sum(x['amount'] for x in expected_cases if x['group']=="N")
    prior_total=sum(x['amount'] for x in expected_cases if x['group']=="P")
    summaryvals=[]
    if wb and "金额汇总" in sheets:
        sm=wb["金额汇总"]
        summaryvals=[sm.cell(r,2).value for r in range(2,8)]
    # Formula text is primary; LibreOffice-cached values are compared when available.
    cached=load_workbook(wb_path,data_only=True) if wb_path.is_file() else None
    cache_sum=False
    if cached and "金额汇总" in cached.sheetnames:
        cv=cached["金额汇总"]["B2"].value; pv=cached["金额汇总"]["B3"].value
        cache_sum=(isinstance(cv,(int,float)) and abs(cv-newtotal)<0.01 and isinstance(pv,(int,float)) and abs(pv-prior_total)<0.01)
    values["A01.workbook_sheets"]={"passed": {"材料索引","案件登记","金额汇总","补件台账"}.issubset(sheets),"actual":sorted(sheets)}
    values["A02.case_count"]={"passed":len(rows)==23,"actual":len(rows)}
    values["A03.new_case_count"]={"passed":sum(1 for x in rows.values() if x.get("公告分组")=="本次新案")==sum(1 for m in expected_cases if m["group"]=="N"),"actual":sum(1 for x in rows.values() if x.get("公告分组")=="本次新案")}
    values["A04.prior_case_count"]={"passed":sum(1 for x in rows.values() if x.get("公告分组")=="前期披露案件")==sum(1 for m in expected_cases if m["group"]=="P"),"actual":sum(1 for x in rows.values() if x.get("公告分组")=="前期披露案件")}
    values["A05.case_codes"]={"passed":ids_present and len(rows)==23,"actual":len(rows)}
    values["A06.case_pages"]={"passed":page_ok,"actual":"逐案登记页码字段"}
    values["A07.case_dockets"]={"passed":docket_ok,"actual":"逐案案号与可信枚举比较"}
    values["A08.case_amounts"]={"passed":amount_ok,"actual":"逐案万元金额与可信枚举比较"}
    values["A09.new_total"]={"passed":formula_ok and (cache_sum or not cached),"actual":{"formula":summaryvals[:1],"expected":newtotal,"cached_matches":cache_sum}}
    values["A10.prior_total"]={"passed":formula_ok and (cache_sum or not cached),"actual":{"formula":summaryvals[1:2],"expected":prior_total,"cached_matches":cache_sum}}
    values["A11.profit_impact"]={"passed": wb is not None and "金额汇总" in sheets and wb["金额汇总"]["B5"].value==204.62 and "未经审计" in str(wb["金额汇总"]["C5"].value),"actual":"工作簿利润影响值与未经审计限定语"}
    values["A12.formula_linkage"]={"passed":formula_ok and (cache_sum or not cached),"actual":{"formulas":summaryvals[:3],"cached_matches":cache_sum}}
    values["A13.P06_cross_page"]={"passed": norm(rows.get("ANN-20260822-P06",{}).get("案号（公告）"))=="(2025)渝0156民初696号" and "2,3" in norm(rows.get("ANN-20260822-P06",{}).get("公告页码")),"actual":"P06登记案号和页码"}
    values["A14.P07_appeal"]={"passed":all(x in norm(rows.get("ANN-20260822-P07",{}).get("公告所述进展")) for x in ["7,433.64","5,758.31"]),"actual":"P07一审/二审金额"}
    values["A15.P08_distribution"]={"passed":"2,856.23" in norm(rows.get("ANN-20260822-P08",{}).get("公告所述进展")) and "结案" in norm(rows.get("ANN-20260822-P08",{}).get("公告所述进展")),"actual":"破产分配金额和结案状态"}
    values["A16.P10_priority"]={"passed":"11,686.18" in norm(rows.get("ANN-20260822-P10",{}).get("公告所述进展")) and "撤诉" in norm(rows.get("ANN-20260822-P10",{}).get("公告所述进展")),"actual":"确认债权金额和撤诉"}
    values["A17.P12_amounts"]={"passed":all(x in norm(rows.get("ANN-20260822-P12",{}).get("公告所述进展")) for x in ["2,084.32","76.93","218.45","3,997.21","5,095.08"]),"actual":"P12登记金额分层"}
    values["A18.P12_counterclaim"]={"passed":"反诉" in norm(rows.get("ANN-20260822-P12",{}).get("公告所述进展")) and "第三人" in norm(rows.get("ANN-20260822-P12",{}).get("被告（公告）")),"actual":"P12反诉与第三人信息"}
    values["A19.P14_party"]={"passed":"郑俊亮" in norm(rows.get("ANN-20260822-P14",{}).get("原告（公告）")) and "非当事人" in norm(rows.get("ANN-20260822-P14",{}).get("公告所述进展")),"actual":"郑俊亮身份提示"}
    values["A20.P16_transfer"]={"passed":"移送" in norm(rows.get("ANN-20260822-P16",{}).get("公告所述进展")) and "兰州" in norm(rows.get("ANN-20260822-P16",{}).get("公告所述进展")),"actual":"P16移送信息"}
    values["A21.P19_amount_split"]={"passed":all(x in norm(rows.get("ANN-20260822-P19",{}).get("公告所述进展")) for x in ["351.91","361.65","100.13"]),"actual":"P19登记金额分项"}
    values["A22.catalog_all_cases"]={"passed":all(code in norm(cat) and norm(meta['case_no']) in norm(cat) for meta in expected_cases for code in [f"ANN-20260822-{'N' if meta['group']=='N' else 'P'}{meta['number']:02d}"]),"actual":"目录逐项码与案号"}
    values["A23.catalog_scope"]={"passed": "不替代" in cat and "公告" in cat and "原始证据" in cat,"actual":"目录范围限定"}
    values["A24.supplement_contract"]={"passed":all(x in note for x in ["施工合同","补充协议","招投标"]),"actual":"合同类补件"}
    values["A25.supplement_performance"]={"passed":all(x in note for x in ["施工日志","签证变更","验收","结算"]),"actual":"履行结算类补件"}
    values["A26.supplement_notice"]={"passed":all(x in note for x in ["催款通知","送达凭证","保修"]),"actual":"通知及保修类补件"}
    values["A27.supplement_procedure"]={"passed":all(x in note for x in ["举证通知","判决","调解书"]),"actual":"程序裁判材料补件"}
    values["A28.supplement_P12"]={"passed":"5,095.08" in note and "P12" in note,"actual":"P12专项补件"}
    values["A29.role_separation"]={"passed": all(w in tnorm for w in ["公告转述","公告摘要","待原件核实"]),"actual":"区分公告转述和原始核验"}
    values["A30.mapping"]={"passed":all(code in norm(cat) and f"{'N' if meta['group']=='N' else 'P'}{meta['number']:02d}" in norm(cat) for meta in expected_cases for code in [f"ANN-20260822-{'N' if meta['group']=='N' else 'P'}{meta['number']:02d}"]),"actual":"目录内部码到N/P提交编号"}
    values["A31.timeline_empty_dates"]={"passed":casews is not None and all(rows[c].get("程序事件日") in (None,"") for c in rows),"actual":"程序事件日空值"}
    values["A32.no_overclaim"]={"passed":("不代表判决金额" in norm(cat) or "不可直接理解为判决金额" in norm(cat)) and ("不代表" in note or "不支持" in note),"actual":"涉案金额口径限制"}
    values["A33.party_court_cause"]={"passed":identity_ok,"actual":"23案原告/被告/案由/法院逐项比对公告登记"}
    values["A34.submission_ids"]={"passed":ids_present and all(f"{'N' if m['group']=='N' else 'P'}{m['number']:02d}" in norm(rows[f"ANN-20260822-{'N' if m['group']=='N' else 'P'}{m['number']:02d}"].get("提交编号")) and f"{'N' if m['group']=='N' else 'P'}{m['number']:02d}" in norm(cat) for m in expected_cases),"actual":"工作簿与目录N/P提交编号映射"}
    return values, candidate_errors


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input-data",required=True,type=Path)
    ap.add_argument("--output",required=True,type=Path)
    ap.add_argument("--logs",required=True,type=Path)
    args=ap.parse_args()
    logs=args.logs; logs.mkdir(parents=True,exist_ok=True)
    reward_path=logs/"reward.json"; report_path=logs/"report.json"
    for p in [reward_path,report_path]:
        try:p.unlink()
        except FileNotFoundError:pass
    try:
        checks,candidate_errors=check_candidate(args.input_data,args.output)
    except (RuntimeError, OSError, ValueError, KeyError) as exc:
        report={"status":"verifier_failure","valid":False,"error":f"{type(exc).__name__}: {exc}","reward":None,"P":None,"S":34,"assertions":[]}
        report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
        return 2
    spec=json.loads(ASSERTIONS_PATH.read_text(encoding="utf-8"))
    S=spec["scale"]
    if S!=len(spec["assertions"]):
        report={"status":"verifier_failure","valid":False,"error":"assertion scale mismatch","reward":None,"P":None,"S":S,"assertions":[]}
        report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
        return 2
    details=[]
    for a in spec["assertions"]:
        actual=checks[a["id"]]
        details.append({"id":a["id"],"kind":a["kind"],"unit":a["unit"],"criterion":a["criterion"],"status":"passed" if actual["passed"] else "failed","actual":actual["actual"],"expected":"assertion-specific condition"})
    P=sum(x["status"]=="passed" for x in details)
    reward=min(1.0,P/S)
    caps=[]
    for ce in spec.get("critical_errors",[]):
        if not checks[ce["assertion"]]["passed"]:
            reward=min(reward,ce["cap"]);caps.append(ce["id"])
    missing=[p for p in [args.output/"evidence_workbook.xlsx",args.output/"evidence_catalog.pdf",args.output/"supplementation_note.pdf"] if not p.is_file()]
    status="graded_candidate_defect" if missing or candidate_errors else "graded"
    report={"status":status,"valid":True,"reward":reward,"P":P,"S":S,"assertions":details,"critical_error_caps":caps,"missing_artifacts":[p.name for p in missing],"candidate_artifact_errors":candidate_errors}
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    reward_path.write_text(json.dumps({"reward":reward},ensure_ascii=False)+"\n",encoding="utf-8")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
