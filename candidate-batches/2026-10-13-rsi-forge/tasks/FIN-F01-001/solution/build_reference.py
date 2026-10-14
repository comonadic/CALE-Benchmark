#!/usr/bin/env python3
import argparse
import subprocess
import tempfile
from pathlib import Path

from docx import Document
from docx.shared import Pt
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from pypdf import PdfReader

FACTS = [
    ("2025 revenue", "2025年度营业总收入", 128468230914.96, "2025 annual report p.97", "2025年度"),
    ("2024 revenue", "2024年度营业总收入", 114601056662.29, "2025 annual report p.97", "2024年度比较"),
    ("2025 cost", "2025年度营业成本", 115193343614.54, "2025 annual report p.97", "2025年度"),
    ("2025 net income", "2025年度净利润", 4545393791.33, "2025 annual report p.98", "2025年度"),
    ("2025 operating cash flow", "经营活动产生的现金流量净额", 6260377323.22, "2025 annual report p.100", "2025年度"),
    ("2025 investing cash flow", "投资活动产生的现金流量净额", -1341611412.69, "2025 annual report p.101", "2025年度"),
    ("2025 financing cash flow", "筹资活动产生的现金流量净额", -5175899781.88, "2025 annual report p.101", "2025年度"),
    ("2025 cash", "货币资金及现金等价物", 3202836313.58, "2025 annual report p.92-93", "2025-12-31"),
    ("2025 receivables", "应收账款", 2978763231.09, "2025 annual report p.92", "2025-12-31"),
    ("2025 inventory", "存货", 11371777008.15, "2025 annual report p.92", "2025-12-31"),
    ("2025 payables", "应付账款", 5726047396.44, "2025 annual report p.94", "2025-12-31"),
    ("2025 fixed assets", "固定资产", 17007956953.83, "2025 annual report p.93", "2025-12-31"),
    ("2025 CIP", "在建工程", 603959168.05, "2025 annual report p.93", "2025-12-31"),
    ("2025 short debt", "短期借款", 1163647077.79, "2025 annual report p.94", "2025-12-31"),
    ("2025 long debt", "长期借款", 249637310.50, "2025 annual report p.95", "2025-12-31"),
    ("2025 total assets", "资产总计", 47590711885.11, "2025 annual report p.93", "2025-12-31"),
    ("2025 total liabilities", "负债合计", 22497894081.53, "2025 annual report p.94", "2025-12-31"),
    ("2025 total equity", "所有者权益合计", 25092817803.58, "2025 annual report p.94", "2025-12-31"),
    ("2026H1 revenue", "营业总收入", 64239967963.30, "2026 half-year report p.61", "2026H1"),
    ("2025H1 revenue", "营业总收入", 58830895138.88, "2026 half-year report p.61", "2025H1比较"),
    ("2026H1 cost", "营业成本", 58236827704.54, "2026 half-year report p.61", "2026H1"),
    ("2026H1 net income", "净利润", 1726556952.59, "2026 half-year report p.62", "2026H1"),
    ("2026H1 operating cash flow", "经营活动产生的现金流量净额", 3923561511.73, "2026 half-year report p.64", "2026H1"),
    ("2026H1 investing cash flow", "投资活动产生的现金流量净额", -2993726149.88, "2026 half-year report p.65", "2026H1"),
    ("2026H1 financing cash flow", "筹资活动产生的现金流量净额", -724819016.92, "2026 half-year report p.65", "2026H1"),
    ("2026H1 cash movement", "现金及现金等价物净增加额", 136480536.53, "2026 half-year report p.65", "2026H1"),
    ("2026H1 cash opening", "期初现金及现金等价物余额", 2998575733.57, "2026 half-year report p.65", "2026-01-01"),
    ("2026H1 cash ending", "期末现金及现金等价物余额", 3135056270.10, "2026 half-year report p.65", "2026-06-30"),
    ("2026H1 AR", "应收账款", 5411032161.70, "2026 half-year report p.56", "2026-06-30"),
    ("2026H1 inventory", "存货", 13917906683.60, "2026 half-year report p.56", "2026-06-30"),
    ("2026H1 AP", "应付账款", 7317868613.15, "2026 half-year report p.57", "2026-06-30"),
    ("2026H1 fixed assets", "固定资产", 16764113281.15, "2026 half-year report p.56", "2026-06-30"),
    ("2026H1 CIP", "在建工程", 870886016.42, "2026 half-year report p.56", "2026-06-30"),
    ("2026H1 short debt", "短期借款", 3601033153.61, "2026 half-year report p.57", "2026-06-30"),
    ("2026H1 long debt", "长期借款", 249637310.50, "2026 half-year report p.57", "2026-06-30"),
    ("2026H1 total assets", "资产总计", 55290906075.56, "2026 half-year report p.56", "2026-06-30"),
    ("2026H1 total liabilities", "负债合计", 30198088271.98, "2026 half-year report p.57", "2026-06-30"),
    ("2026H1 total equity", "所有者权益合计", 25092817803.58, "2026 half-year report p.57", "2026-06-30"),
]


def extract_text(pdf):
    return "\n".join(page.extract_text() or "" for page in PdfReader(str(pdf)).pages)


def style_sheet(ws):
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="315A62")
    for col in ws.columns:
        width = min(72, max(13, max(len(str(c.value or "")) for c in col) + 2))
        ws.column_dimensions[get_column_letter(col[0].column)].width = width
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(vertical="top", wrap_text=True)
            if isinstance(c.value, (float, int)):
                c.number_format = '#,##0.00;[Red]-#,##0.00'


def build(input_dir, output_dir):
    annual = extract_text(input_dir / "haid_group_2025_annual_report.pdf")
    half = extract_text(input_dir / "haid_group_2026_half_year_report.pdf")
    if "营业总收入" not in annual or "资产总计" not in half or "2026 年 06 月 30 日" not in half:
        raise ValueError("Required report markers missing")

    wb = Workbook()
    hist = wb.active
    hist.title = "历史数据"
    hist.append(["指标", "披露项目", "期间", "金额（人民币元）", "主体与范围", "来源及PDF页码"])
    values = {}
    hist_rows = {}
    for label, metric, value, citation, period in FACTS:
        hist.append([label, metric, period, value, "广东海大集团股份有限公司；合并口径", citation])
        values[label] = value
        hist_rows[label] = hist.max_row

    assumptions = wb.create_sheet("情景假设")
    assumptions.append(["参数", "数值", "单位/依据與性质"])
    assumption_rows = {}
    assumption_data = [
        ("H2收入增速", 0.04, "百分比；分析者情景，可编辑；非公司预算/指引"),
        ("营业成本率", values["2026H1 cost"] / values["2026H1 revenue"], "H1披露营业成本/收入；情景基准"),
        ("应收账款/收入", values["2026H1 AR"] / values["2026H1 revenue"], "H1期末余额/H1收入；简化情景基准"),
        ("存货/收入", values["2026H1 inventory"] / values["2026H1 revenue"], "H1期末余额/H1收入；简化情景基准"),
        ("应付账款/成本", values["2026H1 AP"] / values["2026H1 cost"], "H1期末余额/H1营业成本；简化情景基准"),
        ("资本开支", 1692678370.48, "人民币元；H1现金流披露购建长期资产支出作为H2情景输入"),
        ("折旧", 515096879.40, "人民币元；H1披露固定资产折旧作为H2情景输入"),
        ("净新增借款", 0.0, "人民币元；分析者情景参数，缺少逐笔融资计划"),
        ("现金股利", 0.0, "人民币元；分析者情景参数，未假设未来分红"),
        ("所得税率", 0.25, "比例；简化分析者情景参数"),
        ("分析敏感性增速变动", 0.01, "百分点；对H2收入增速上调1个百分点"),
    ]
    for name, val, note in assumption_data:
        assumptions.append([name, val, note])
        assumption_rows[name] = assumptions.max_row

    wc = wb.create_sheet("营运资本")
    wc.append(["项目", "H1期末实际", "驱动参数", "H2情景期末", "余额变动"])
    wc_specs = [
        ("应收账款", values["2026H1 AR"], "='情景假设'!B4"),
        ("存货", values["2026H1 inventory"], "='情景假设'!B5"),
        ("应付账款", values["2026H1 AP"], "='情景假设'!B6"),
    ]
    for i, (name, actual, ratio) in enumerate(wc_specs, start=2):
        base = "'利润表'!B2" if name != "应付账款" else "'利润表'!B3"
        wc.append([name, actual, ratio, f"={base}*C{i}", f"=D{i}-B{i}"])

    fa = wb.create_sheet("固定资产与债务")
    fa.append(["项目", "2026H1期末实际", "H2增加/变动", "H2期末情景", "滚动公式"])
    fa.append(["固定资产净额", values["2026H1 fixed assets"], "='情景假设'!B7-'情景假设'!B8", "=B2+C2", "期初+资本开支-折旧"])
    debt_open = values["2026H1 short debt"] + values["2026H1 long debt"]
    fa.append(["借款合计", debt_open, "='情景假设'!B9", "=B3+C3", "期初+净新增借款"])
    fa.append(["短期借款", values["2026H1 short debt"], 0, "=B4+C3", "净新增借款简化计入短期借款"])
    fa.append(["长期借款", values["2026H1 long debt"], 0, "=B5", "H2情景不变"])

    pl = wb.create_sheet("利润表")
    pl.append(["项目", "2026H2分析情景"])
    pl.append(["营业收入", f"='历史数据'!D{hist_rows['2026H1 revenue']}*(1+'情景假设'!B2)"])
    pl.append(["营业成本", "=B2*'情景假设'!B3"])
    pl.append(["折旧费用", "='情景假设'!B8"])
    pl.append(["税前简化利润", "=B2-B3-B4"])
    pl.append(["所得税", "=MAX(0,B5*'情景假设'!B11)"])
    pl.append(["净利润", "=B5-B6"])

    cf = wb.create_sheet("现金流量表")
    cf.append(["项目", "2026H2分析情景"])
    cf.append(["净利润", "='利润表'!B7"])
    cf.append(["加：折旧", "='利润表'!B4"])
    cf.append(["营运资本现金流影响", "=-'营运资本'!E2-'营运资本'!E3+'营运资本'!E4"])
    cf.append(["经营活动现金流净额（简化）", "=SUM(B2:B4)"])
    cf.append(["资本开支", "=-'情景假设'!B7"])
    cf.append(["净新增借款", "='情景假设'!B9"])
    cf.append(["支付股利", "=-'情景假设'!B10"])
    cf.append(["现金净变动", "=SUM(B5:B8)"])
    cf.append(["期初现金及现金等价物", values["2026H1 cash ending"]])
    cf.append(["期末现金及现金等价物", "=B9+B10"])

    bs = wb.create_sheet("资产负债表")
    bs.append(["项目", "2026H2情景期末"])
    bs.append(["现金", "='现金流量表'!B11"])
    bs.append(["应收账款", "='营运资本'!D2"])
    bs.append(["存货", "='营运资本'!D3"])
    bs.append(["固定资产净额", "='固定资产与债务'!D2"])
    bs.append(["其他资产（未逐项预测汇总）", f"='历史数据'!D{hist_rows['2026H1 total assets']}-'历史数据'!D{hist_rows['2026H1 cash ending']}-'历史数据'!D{hist_rows['2026H1 AR']}-'历史数据'!D{hist_rows['2026H1 inventory']}-'历史数据'!D{hist_rows['2026H1 fixed assets']}"])
    bs.append(["资产总计", "=SUM(B2:B6)"])
    bs.append(["应付账款", "='营运资本'!D4"])
    bs.append(["借款合计", "='固定资产与债务'!D3"])
    bs.append(["其他负债（未逐项预测汇总）", f"='历史数据'!D{hist_rows['2026H1 total liabilities']}-'历史数据'!D{hist_rows['2026H1 AP']}-'历史数据'!D{hist_rows['2026H1 short debt']}-'历史数据'!D{hist_rows['2026H1 long debt']}"])
    bs.append(["权益", f"='历史数据'!D{hist_rows['2026H1 total equity']}+'利润表'!B7-'情景假设'!B10"])
    bs.append(["负债和权益", "=SUM(B8:B11)"])
    bs.append(["平衡差额（资产-负债及权益）", "=B7-B12"])

    check = wb.create_sheet("检查")
    check.append(["检查项目", "计算结果", "通过标准/说明"])
    check.append(["2026H1现金滚动差额", f"='历史数据'!D{hist_rows['2026H1 cash opening']}+'历史数据'!D{hist_rows['2026H1 cash movement']}-'历史数据'!D{hist_rows['2026H1 cash ending']}", "绝对值≤1元"])
    check.append(["H2现金滚动差额", "='现金流量表'!B9+'现金流量表'!B10-'现金流量表'!B11", "绝对值≤1元"])
    check.append(["H2资产负债差额", "='资产负债表'!B13", "绝对值≤1元；差额显示模型未建模项的滚动限制"])
    check.append(["借款滚动差额", "='固定资产与债务'!D3-'固定资产与债务'!B3-'固定资产与债务'!C3", "绝对值≤1元"])
    check.append(["固定资产滚动差额", "='固定资产与债务'!D2-'固定资产与债务'!B2-'固定资产与债务'!C2", "绝对值≤1元"])
    check.append(["权益滚动差额", f"='资产负债表'!B11-'历史数据'!D{hist_rows['2026H1 total equity']}-'利润表'!B7+'情景假设'!B10", "绝对值≤1元"])
    check.append(["H2收入增速+1个百分点影响", "='历史数据'!D" + str(hist_rows['2026H1 revenue']) + "*(1+'情景假设'!B2+'情景假设'!B12)-'利润表'!B2", "大于0；公式直接引用敏感性参数"])
    check.append(["联动说明", "收入驱动成本及应收/存货；成本驱动应付；资本开支和折旧滚动固定资产；净利润、营运资本变化、资本开支、借款与股利驱动现金；净利润及股利驱动权益。", "分析者情景；其他资产与负债暂按H1余额汇总，未逐项预测"])

    notes = wb.create_sheet("说明")
    notes.append(["主题", "内容"])
    notes.append(["主体、期间与单位", "广东海大集团股份有限公司合并口径；人民币元。年报提供2025/2024年度数据；半年报提供2026H1及2025H1比较数据。流量为对应期间发生额，资产负债项目为期末余额。"])
    notes.append(["历史来源", "每项历史事实均列出报告名及PDF显示页码；引用页码采用报告印刷页码。年报与半年报期末数按各自披露口径记录。"])
    notes.append(["情景假设", "H2增速、资本开支、折旧、借款、股利和税率是可编辑分析参数，非公司预算、指引或批准计划。成本率与营运资本比例以H1披露数据作为简化基准。"])
    notes.append(["三表联动", "H2利润表、营运资本、固定资产、债务、现金和权益支持表以公式连接。H2现金流采用简化间接法；未逐项建模的经营、投资、融资及综合收益事项会影响预测精度。"])
    notes.append(["模型限制", "公开资料未提供既有模型、批准预算、逐笔债务或获批资本开支计划；H2现金流为简化间接法，其他资产与其他负债先按H1汇总余额持平。该处理仅用于明确展示预测联动和滚动差额，不代表完整资产负债预测或经营计划。"])

    for ws in wb.worksheets:
        style_sheet(ws)
    output_dir.mkdir(parents=True, exist_ok=True)
    xlsx = output_dir / "three_statement_model.xlsx"
    wb.calculation.fullCalcOnLoad = True
    wb.calculation.forceFullCalc = True
    wb.calculation.calcMode = "auto"
    wb.save(xlsx)
    with tempfile.TemporaryDirectory() as td:
        recalced_dir = Path(td) / "recalced"
        recalced_dir.mkdir()
        profile = Path(td) / "lo-profile"
        subprocess.run(["soffice", "--headless", f"-env:UserInstallation=file://{profile}", "--convert-to", "xlsx", "--outdir", str(recalced_dir), str(xlsx)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        recalced = recalced_dir / xlsx.name
        if recalced.exists():
            recalced.replace(xlsx)

    values_wb = load_workbook(xlsx, data_only=True)
    check_values = {values_wb["检查"].cell(r, 1).value: values_wb["检查"].cell(r, 2).value for r in range(2, values_wb["检查"].max_row + 1)}
    notes["B6"] = "H2情景结果：期末现金约{:.2f}元；期末权益约{:.2f}元；资产负债差额{:.2f}元；增速敏感性收入影响{:.2f}元。检查差额保留用于识别其他资产/负债简化持平的局限。".format(values_wb["现金流量表"]["B11"].value, values_wb["资产负债表"]["B11"].value, values_wb["资产负债表"]["B13"].value, check_values["H2收入增速+1个百分点影响"])
    wb_summary = load_workbook(xlsx)
    wb_summary["说明"]["B7"] = notes["B6"].value
    wb_summary.save(xlsx)
    with tempfile.TemporaryDirectory() as td:
        recalced_dir = Path(td) / "recalced"
        recalced_dir.mkdir()
        profile = Path(td) / "lo-profile"
        subprocess.run(["soffice", "--headless", f"-env:UserInstallation=file://{profile}", "--convert-to", "xlsx", "--outdir", str(recalced_dir), str(xlsx)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        recalced = recalced_dir / xlsx.name
        if recalced.exists():
            recalced.replace(xlsx)

    doc = Document()
    doc.add_heading("海大集团三表模型更新说明", 0)
    report_sections = [
        ("口径与来源", "人民币元、合并口径；历史数据来自2025年年度报告及2026年半年度报告，工作簿逐项列示报告及PDF页码。流量和时点数按披露期间区分。"),
        ("情景参数性质", "H2收入增速、资本开支、折旧、借款、股利及税率为可编辑分析者情景，不是公司批准预算或业绩指引。成本及营运资本率以H1实际比例作简化基准。"),
        ("模型与结果", "工作簿公式联动收入、成本、营运资本、固定资产、借款、现金流及权益。检查页列示H1/H2现金滚动、预测资产负债差额、支持表滚动和收入增速上调1个百分点的敏感性。"),
        ("限制", "未取得既有模型、批准预算、逐笔债务台账或资本开支计划。经营现金流采用简化间接法，其他资产/负债按H1汇总余额暂时持平；资产负债差额作为诊断，不作平衡插值。"),
    ]
    for title, text in report_sections:
        doc.add_heading(title, 1)
        p = doc.add_paragraph(text)
        p.paragraph_format.space_after = Pt(8)
    doc.add_paragraph(notes["B6"].value)
    docx = output_dir / "model_update_notes.docx"
    doc.save(docx)
    with tempfile.TemporaryDirectory() as td:
        profile = Path(td) / "lo-profile"
        subprocess.run(["libreoffice", "--headless", f"-env:UserInstallation=file://{profile}", "--convert-to", "pdf", "--outdir", str(output_dir), str(docx)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    docx.unlink(missing_ok=True)
    values_wb.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.input_data, args.output)
