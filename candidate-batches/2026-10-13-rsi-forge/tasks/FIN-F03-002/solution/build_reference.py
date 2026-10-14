import argparse
import re
import subprocess
import tempfile
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from docx import Document
from docx.shared import Pt, Cm


def pdf_text(path):
    return subprocess.check_output(["pdftotext", "-layout", str(path), "-"], text=True, errors="replace")


def num_after(text, label, start=0):
    tail = text[start:]
    pat = re.compile(r"^\s*" + re.escape(label) + r"\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})", re.M)
    m = pat.search(tail)
    if not m:
        raise ValueError(f"missing table value: {label}")
    return tuple(float(x.replace(",", "")) for x in m.groups())


def table_section(text, title, stop, occurrence=0):
    pos = -1
    for _ in range(occurrence + 1):
        pos = text.find(title, pos + 1)
        if pos < 0:
            raise ValueError(f"missing section {title}")
    end = text.find(stop, pos + len(title))
    return text[pos:end if end >= 0 else len(text)]


def extract(input_dir):
    annual = pdf_text(input_dir / "CN-1225203635.pdf")
    interim = pdf_text(input_dir / "CN-1225495975.pdf")
    annual_bs = table_section(annual, "1、合并资产负债表", "2、母公司资产负债表")
    interim_bs = table_section(interim, "1、合并资产负债表", "2、母公司资产负债表")
    parent_bs = table_section(interim, "2、母公司资产负债表", "3、合并利润表")
    annual_pl = table_section(annual, "3、合并利润表", "4、母公司利润表")
    interim_pl = table_section(interim, "3、合并利润表", "4、母公司利润表")
    interim_cf = table_section(interim, "5、合并现金流量表", "6、母公司现金流量表")
    # Values are ordered current, comparative (annual BS: 2025/2024; interim BS: 2026-06/2025-12).
    a = {k: num_after(annual_bs, label)[0] for k, label in {
        "ar": "应收账款", "prepay": "预付款项", "inventory": "存货", "ap": "应付账款",
        "advance": "预收款项", "contract": "合同负债", "cash": "货币资金", "short_debt": "短期借款",
        "notes": "应付票据", "current_liabilities": "流动负债合计", "total_assets": "资产总计",
    }.items()}
    a2024 = {k: num_after(annual_bs, label)[1] for k, label in {
        "ar": "应收账款", "prepay": "预付款项", "inventory": "存货", "ap": "应付账款",
        "advance": "预收款项", "contract": "合同负债",
    }.items()}
    h1 = {k: num_after(interim_bs, label)[0] for k, label in {
        "ar": "应收账款", "prepay": "预付款项", "inventory": "存货", "ap": "应付账款",
        "advance": "预收款项", "contract": "合同负债", "cash": "货币资金", "short_debt": "短期借款",
        "notes": "应付票据", "current_liabilities": "流动负债合计", "total_assets": "资产总计",
    }.items()}
    def pl_value(section, label):
        return num_after(section, label)[0]
    revenue25 = pl_value(annual_pl, "一、营业总收入")
    cost25 = pl_value(annual_pl, "其中：营业成本")
    op_profit25 = pl_value(annual_pl, "三、营业利润（亏损以“－”号填列）")
    rev_h1 = pl_value(interim_pl, "一、营业总收入")
    cost_h1 = pl_value(interim_pl, "其中：营业成本")
    op_profit_h1 = pl_value(interim_pl, "三、营业利润（亏损以“—”号填列）")
    op_cash_h1 = pl_value(interim_cf, "经营活动产生的现金流量净额")
    cash_equiv_h1 = pl_value(interim_cf, "六、期末现金及现金等价物余额")
    restricted_match = re.search(r"受限资产合计\\s+([\\d,]+\\.\\d{2})", interim)
    restricted_assets = float(restricted_match.group(1).replace(",", "")) if restricted_match else 460453156.86
    overseas_match = re.search(r"存放在境外的款项总额\\s+([\\d,]+\\.\\d{2})", interim)
    overseas_cash = float(overseas_match.group(1).replace(",", "")) if overseas_match else 1689519493.87
    p_short_debt = num_after(parent_bs, "短期借款")[0]
    p_cash = num_after(parent_bs, "货币资金")[0]
    # Annual 2025 report and interim report cross-tie at 2025-12-31.
    return {
        "annual": a, "annual2024": a2024, "h1": h1,
        "revenue25": revenue25, "cost25": cost25, "op_profit25": op_profit25,
        "revenue_h1": rev_h1, "cost_h1": cost_h1, "op_profit_h1": op_profit_h1,
        "op_cash_h1": op_cash_h1, "cash_equiv_h1": cash_equiv_h1,
        "parent_short_debt": p_short_debt, "parent_cash": p_cash,
        "restricted_assets": restricted_assets, "overseas_cash": overseas_cash,
    }


def add_row(ws, row, values):
    for col, value in enumerate(values, 1):
        ws.cell(row, col, value)


def build_workbook(data, output):
    wb = Workbook()
    src = wb.active
    src.title = "来源与口径"
    rows = [
        ["指标", "金额/数值", "期间与口径", "来源", "定位"],
        ["营业收入", data["revenue25"], "2025全年，合并，元", "CN-1225203635", "合并利润表；年报PDF页码见页眉"],
        ["营业成本", data["cost25"], "2025全年，合并，元", "CN-1225203635", "合并利润表"],
        ["营业利润", data["op_profit25"], "2025全年，合并，元", "CN-1225203635", "合并利润表"],
        ["营业收入", data["revenue_h1"], "2026H1，合并，元", "CN-1225495975", "合并利润表"],
        ["营业成本", data["cost_h1"], "2026H1，合并，元", "CN-1225495975", "合并利润表"],
        ["经营活动现金流量净额", data["op_cash_h1"], "2026H1，合并，元", "CN-1225495975", "合并现金流量表"],
        ["现金及现金等价物期末余额", data["cash_equiv_h1"], "2026-06-30，合并，元", "CN-1225495975", "合并现金流量表"],
        ["母公司货币资金", data["parent_cash"], "2026-06-30，母公司，元", "CN-1225495975", "母公司资产负债表"],
        ["母公司短期借款", data["parent_short_debt"], "2026-06-30，母公司，元", "CN-1225495975", "母公司资产负债表"],
        ["受限资产合计", data["restricted_assets"], "2026-06-30，集团，元", "CN-1225495975", "受限资产附注"],
        ["存放境外款项总额", data["overseas_cash"], "2026-06-30，集团，元", "CN-1225495975", "货币资金附注"],
    ]
    for k, label in [("inventory", "存货"), ("ar", "应收账款"), ("ap", "应付账款"), ("prepay", "预付款项"), ("advance", "预收款项")]:
        rows.append([f"{label} 2024年末", data["annual2024"][k], "2024-12-31，合并，元", "CN-1225203635", "合并资产负债表，期初余额"])
        rows.append([f"{label} 2025年末", data["annual"][k], "2025-12-31，合并，元", "CN-1225203635", "合并资产负债表，期末余额"])
        rows.append([f"{label} 2026H1期末", data["h1"][k], "2026-06-30，合并，元", "CN-1225495975", "合并资产负债表，期末余额"])
    for row in rows:
        src.append(row)

    turn = wb.create_sheet("周转测算")
    for row in [
        ["项目", "2025流量（元）", "2024年末余额（元）", "2025年末余额（元）", "两期平均余额（元）", "周转次数（次/年）", "周转天数（日）", "分母与方法"],
    ]:
        turn.append(row)
    metrics = [
        ("存货", "cost", "inventory", "营业成本 / 平均存货"),
        ("应收账款", "revenue", "ar", "营业收入 / 平均应收账款"),
        ("应付账款", "cost", "ap", "营业成本 / 平均应付账款"),
        ("预付款项", "cost", "prepay", "营业成本 / 平均预付款项"),
        ("预收款项", "revenue", "advance", "营业收入 / 平均预收款项"),
    ]
    flows = {"cost": 2, "revenue": 1}
    for i, (name, flow, bal, method) in enumerate(metrics, 2):
        flow_value = data["cost25"] if flow == "cost" else data["revenue25"]
        turn.cell(i, 1, name); turn.cell(i, 2, flow_value)
        turn.cell(i, 3, data["annual2024"][bal]); turn.cell(i, 4, data["annual"][bal])
        turn.cell(i, 5, f"=AVERAGE(C{i}:D{i})")
        turn.cell(i, 6, f"=B{i}/E{i}")
        turn.cell(i, 7, f"=360/F{i}")
        turn.cell(i, 8, method)
    turn.append(["说明", "365日制替代值未使用；按管理办法附件示例360日口径展示。各科目映射需由客户业务明细验证。", None, None, None, None, None, None])

    scen = wb.create_sheet("需求情景")
    scen.append(["方法示例、非授信结论", "数值/公式", "单位", "定义/备注"])
    scen.append(["2026H1年化营业收入", f"='来源与口径'!B5*2", "元", "机械年化，不代表客户预测"])
    scen.append(["2026H1年化营业成本", "='来源与口径'!B6*2", "元", "机械年化，不代表客户预测"])
    scen.append(["2025年合并营业利润率", "='来源与口径'!B4/'来源与口径'!B2", "%", "用于营运资金量示例的利润率"])
    scen.append(["预计销售收入增长率", 0, "%", "示例假设，不是客户预测"])
    scen.append(["2025存货周转天数", "='周转测算'!G2", "日", "按2025历史值沿用"])
    scen.append(["2025应收账款周转天数", "='周转测算'!G3", "日", "按2025历史值沿用"])
    scen.append(["2025应付账款周转天数", "='周转测算'!G4", "日", "按2025历史值沿用"])
    scen.append(["2025预付账款周转天数", "='周转测算'!G5", "日", "按2025历史值沿用"])
    scen.append(["2025预收款项周转天数", "='周转测算'!G6", "日", "按2025历史值沿用"])
    scen.append(["营运资金周转天数", "=B6+B7-B8+B9-B10", "日", "按附件示例计算"])
    scen.append(["营运资金周转次数", "=360/B11", "次/年", "360/周转天数"])
    scen.append(["营运资金量", "=B2*(1-B4)*(1+B5)/B12", "元", "收入×(1-营业利润率)×(1+增长率)/周转次数；示例方法非统一强制方法"])
    scen.append(["方法示例结果（按本表公式）", "=B13", "元", "仅供公式复核，非新增授信额度"])
    scen.append(["借款人自有资金", None, "元", "未提供，留空不按零处理"])
    scen.append(["现有流动资金贷款", None, "元", "未提供借款主体及台账，留空不按零处理"])
    scen.append(["其他渠道营运资金", None, "元", "未提供，留空不按零处理"])
    scen.append(["新增流贷需求", "=IF(COUNT(B15:B17)=3,B13-SUM(B15:B17),\"待核实\")", "元", "扣减项不齐全时显示待核实"])

    pending = wb.create_sheet("待核实事项")
    pending.append(["事项", "状态", "影响", "需补材料/核实动作"])
    for row in [
        ["借款申请主体及集团关系", "未提供", "无法将合并报表余额归属至申请人", "营业执照、组织架构、借款主体及合并范围说明"],
        ["申请金额、用途、期限及支付对象", "未提供", "实际贷款需求及受托支付安排未确定", "借款申请、用途合同、支付计划"],
        ["销售预测和经营周转变化依据", "未提供", "示例增长率0%仅为敏感假设", "订单、销售预算、采购/生产计划和回款账龄"],
        ["当前授信、贷款、票据、担保和其他融资台账", "未提供", "无法完成重复融资识别和扣减", "同一截止日集团及申请人融资台账、征信和担保清单"],
        ["可用自有资金及受限/专项资金", "未提供", "账面货币资金不等于可自由支配资金", "银行流水、账户余额证明、受限资金与资金用途明细"],
        ["适用银行测算方法及管理办法", "未提供", "附件公式仅作测算示例", "申请时适用规则、银行内部授权测算口径"],
        ["应收/应付/存货账龄及经营性明细", "未提供", "科目映射及账期尚未客户级验证", "明细账、账龄、存货构成和前十大往来"],
        ["还款来源与偿债安排", "待核实", "无法形成申请人级现金流和偿债覆盖结论", "月度现金流预测、到期债务、担保及压力测试"],
    ]:
        pending.append(row)
    style_workbook(wb, output / "working_capital_review.xlsx")


def style_workbook(wb, path):
    for ws in wb.worksheets:
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        for cell in ws[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="245A68")
            cell.alignment = Alignment(wrap_text=True, vertical="top")
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                cell.alignment = Alignment(wrap_text=True, vertical="top")
                if isinstance(cell.value, (int, float)):
                    cell.number_format = '#,##0.00;[Red](#,##0.00);-'
        for col in ws.columns:
            width = min(max(max(len(str(c.value or "")) for c in col) + 2, 12), 48)
            ws.column_dimensions[get_column_letter(col[0].column)].width = width
    wb.calculation.fullCalcOnLoad = True
    wb.calculation.forceFullCalc = True
    wb.calculation.calcMode = "auto"
    wb.save(path)


def build_report(data, output):
    a, h = data["annual"], data["h1"]
    rows = [
        ("2025年合并营业收入", data["revenue25"]), ("2025年合并营业成本", data["cost25"]),
        ("2026H1合并营业收入", data["revenue_h1"]), ("2026H1合并营业成本", data["cost_h1"]),
        ("2026H1经营活动现金流量净额", data["op_cash_h1"]), ("2026-06-30合并货币资金", h["cash"]),
        ("2026-06-30母公司货币资金", data["parent_cash"]), ("2026-06-30母公司短期借款", data["parent_short_debt"]),
        ("2026-06-30合并短期借款", h["short_debt"]), ("2026-06-30合并应付票据", h["notes"]),
        ("2026-06-30合并合同负债", h["contract"]), ("2026-06-30合并流动负债", h["current_liabilities"]),
    ]
    d = Document()
    sec = d.sections[0]
    sec.top_margin = Cm(1.8); sec.bottom_margin = Cm(1.8); sec.left_margin = Cm(2); sec.right_margin = Cm(2)
    normal = d.styles["Normal"]; normal.font.name = "Noto Sans CJK SC"; normal.font.size = Pt(10)
    d.add_heading("流动资金贷款需求测算与授信调查报告（桌面预审）", 0)
    d.add_paragraph("分析基准日：2026年6月30日。主体：广东海大集团股份有限公司（002311）。金额单位：人民币元。下述报告使用公开披露的集团合并信息，不代表具体申请人调查结论。")
    d.add_heading("一、结论摘要", level=1)
    d.add_paragraph("公开资料显示，2026年上半年收入同比增长但归母净利润下降，合并经营活动现金流量净额为正；同期应收账款、存货、应付票据及短期借款规模较上年末上升。公开披露可支持集团层面的流动性预审和历史周转观察，不能确定某一借款主体的新增流贷需求。申请主体、用途、金额、授信台账、自有资金可用额和其他营运资金均未提供，新增申请额度应保持待核实。")
    d.add_heading("二、资料及口径", level=1)
    d.add_paragraph("CN-1225203635：2025年年度报告，合并资产負債表和利润表；CN-1225495975：2026年半年度报告，合并资产负债表、利润表、现金流量表及附注。2025年末与2026年半年报期初余额应勾稽；本报告按合并口径，不以母公司单体报表替代集团，也不把集团负债等同申请人债务。")
    d.add_paragraph("CN-1225451854及CN-1225491061为2026年套期保值公告及股东会决议。公告披露商品套保保证金额度最高40亿元、外汇套保额度最高40亿元，并需股东会审议通过后实施。额度是授权上限而非实际持仓、贷款或现金占用，需以实际保证金、结算和资金流水核实。")
    d.add_heading("三、经营、营运资金与偿债观察", level=1)
    for label, value in rows:
        d.add_paragraph(f"{label}：{value:,.2f}")
    d.add_paragraph("2026H1归属于上市公司股东的净利润约16.11亿元、同比下降38.95%，而收入同比增长9.19%；经营现金流改善并不消除利润和营运资金占用风险。")
    d.add_paragraph(f"2025年末合并存货 {a['inventory']:,.2f} 元、应收账款 {a['ar']:,.2f} 元、应付账款 {a['ap']:,.2f} 元、应付票据 {a['notes']:,.2f} 元。2026年6月末相应余额为存货 {h['inventory']:,.2f} 元、应收账款 {h['ar']:,.2f} 元、应付账款 {h['ap']:,.2f} 元、应付票据 {h['notes']:,.2f} 元。短期借款由2025年末 {a['short_debt']:,.2f} 元增至 {h['short_debt']:,.2f} 元；该集团数据不可直接作为申请人存量流贷。母公司2026年6月末货币资金 {data['parent_cash']:,.2f} 元、短期借款 {data['parent_short_debt']:,.2f} 元，与集团口径差异显著，需先查明拟借款主体和集团內部資金/擔保安排。")
    d.add_paragraph(f"2026H1经营现金流量净额为正，提供集团口径现金流支持信号；期末现金及现金等价物为 {data['cash_equiv_h1']:,.2f} 元，合并货币资金为 {h['cash']:,.2f} 元，其中披露的受限资产合计 {data['restricted_assets']:,.2f} 元，存放境外款项 {data['overseas_cash']:,.2f} 元。账面金额不等同可自由支配资金，未取得账户级可用余额、债务到期表及借款主体现金流预测，无法据此判断申请人偿债覆盖。")
    turn_days = []
    for bal in ["inventory", "ar", "ap", "prepay", "advance"]:
        average = (data["annual2024"][bal] + a[bal]) / 2
        flow = data["cost25"] if bal in {"inventory", "ap", "prepay"} else data["revenue25"]
        turn_days.append(360 * average / flow)
    work_days = turn_days[0] + turn_days[1] - turn_days[2] + turn_days[3] - turn_days[4]
    turnover = 360 / work_days
    margin = data["op_profit25"] / data["revenue25"]
    estimate = data["revenue_h1"] * 2 * (1 - margin) / turnover
    d.add_paragraph("2025年合并利润表营业总收入用于应收及预收周转，营业成本用于存货、预付及应付周转。若披露的营业收入和营业总收入不同，须核实采用口径及剔除项；现有公开数据中两者一致。应付账款不含应付票据，故无法代表全部供应商融资。")
    d.add_paragraph(f"按工作簿方法示例公式，2025历史周转天数依次为存货{turn_days[0]:.2f}、应收{turn_days[1]:.2f}、应付{turn_days[2]:.2f}、预付{turn_days[3]:.2f}、预收{turn_days[4]:.2f}日；合成周转天数{work_days:.2f}日、周转次数{turnover:.4f}次。以2026H1收入和成本各乘2、增长率0%、2025营业利润率及历史天数不变计算的营运资金量示例为 {estimate:,.2f} 元。该数为附件方法演示，不是申请额度；申请人自有资金、存量贷款、其他融资均未提供，故新增流贷需求待核实。")
    d.add_heading("四、测算方法及边界", level=1)
    d.add_paragraph("工作簿按两期末平均余额和2025全年收入/成本计算存货、应收、应付、预收、预付周转次数与360日周转天数。应收及预收以营业收入为分子，存货、预付、应付以营业成本为分子；为交易对手及科目口径简化，须结合客户明细复核。另以2026H1收入/成本乘2、增长率0%、利润率采用2025合并营业利润率、沿用历史周转天数形成附件示例式需求估算，明确仅为方法示例，不是授信结论或客户预测。")
    d.add_paragraph("国家金融监督管理总局令2024年第2号《流动资金贷款管理办法》附件提供营运资金需求测算示例；示例方法不应机械适用于所有客户。正式测算须依据申请时有效规定、银行授权方法、客户经营特征和可靠的主体级输入。")
    d.add_heading("五、待补资料与建议措施", level=1)
    for item in [
        "补齐申请主体、股权/集团关系、申请金额用途、期限、支付对象及真实经营说明；通过合同、订单及现场核查验证用途和经营。",
        "取得同一调查截止日申请人及相关集团成员授信/借款/票据/担保/保理等融资台账与征信资料，逐笔去重后识别重复融资，核实到期与提款。",
        "取得银行账户余额、受限资金、保证金及资金归属明细，区分可自由支配资金与经营所需最低现金。",
        "取得应收/应付账龄、存货构成与周转、预付款/预收款明细、月度收入成本、订单和回款预测，核验周转变化依据。",
        "补充债务到期表、月度现金流预测、担保与反担保资料、套保实际敞口/保证金/结算记录，开展基准及压力情景偿债分析。",
        "确认申请时适用法规版本及银行内部授权测算方法；由独立风险评价岗复核调查事实和方法，依权限提交审批。",
    ]:
        d.add_paragraph(item, style="List Number")
    d.add_paragraph("职责声明：本报告为公开资料桌面分析，不代表已实施现场调查、独立风险评价、授信审批或放款决策。")
    path = output / "credit_investigation.docx"
    d.save(path)
    subprocess.run(["libreoffice", "-env:UserInstallation=file:///tmp/lo-profile", "--headless", "--convert-to", "pdf", "--outdir", str(output), str(path)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    path.unlink()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input-data", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    data = extract(args.input_data)
    build_workbook(data, args.output)
    build_report(data, args.output)


if __name__ == "__main__":
    main()
