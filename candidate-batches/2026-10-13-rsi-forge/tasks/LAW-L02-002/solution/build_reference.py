#!/usr/bin/env python3
import argparse
import json
import os
import re
import subprocess
from pathlib import Path
from xml.sax.saxutils import escape

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.table import Table, TableStyleInfo
from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import LongTable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table as PdfTable, TableStyle

CASE_META = [
    ("N", 1, "重庆交通建设（集团）有限责任公司", "泸溪县干线公路建设有限责任公司", "建设工程合同纠纷", "(2026)湘3122民初49号", 8966.45, "湖南省泸溪县人民法院", "目前一审审理中。", [1]),
    ("N", 2, "重庆建工", "四川巴中宏德置业有限公司", "建设工程合同纠纷", "(2026)川1902民初4724号", 3332.63, "巴中市巴州区人民法院", "目前一审审理中。", [1]),
    ("N", 3, "重庆建工", "云阳县宏荣路桥工程有限公司", "建设工程施工合同纠纷", "(2026)渝0235民初6507号", 8094.68, "云阳县人民法院", "目前一审审理中。", [2]),
    ("N", 4, "重庆工业设备安装集团有限公司", "赛鼎工程有限公司、阿拉善盟东海新能源实业有限公司、阿拉善盟沪蒙能源实业有限公司", "建设工程施工合同纠纷", "(2026)内29民初5号", 47444.10, "内蒙古自治区阿拉善盟中级人民法院", "目前一审审理中。", [2]),
    ("P", 1, "重庆建工", "毕节市博泰房地产开发有限责任公司", "建设工程施工合同纠纷", "(2017)黔05民初187号", 1534.22, "贵州省毕节市中级人民法院、贵州省高级人民法院", "一审判决被告支付工程款680.64万元、保修金315.56万元及利息；二审驳回上诉、维持原判；被告已履行完毕。", [2]),
    ("P", 2, "重庆建工", "中京博泰毕节地产置业有限公司、毕节市博泰房地产开发有限责任公司", "建设工程施工合同纠纷", "(2017)黔05民初188号", 2668.69, "贵州省毕节市中级人民法院、贵州省高级人民法院", "一审判决支付工程款2,179.04万元（含500.00万元补偿金）及利息、保证金148.15万元及利息；另一被告对补偿金及利息承担连带责任；二审维持原判，已履行完毕。", [2]),
    ("P", 3, "重庆城建控股（集团）有限责任公司", "重庆双驰建筑劳务有限公司、廖世华（第三人）", "建设工程施工合同纠纷", "(2024)皖1202民初8782号", 4677.21, "安徽省阜阳市颍州区人民法院、安徽省阜阳市中级人民法院", "一审驳回原告诉请，二审维持；被告不承担责任。", [2]),
    ("P", 4, "阿勒泰卓渝建筑工程有限责任公司", "贵州西凯三友房地产开发有限公司", "建设工程施工合同纠纷", "(2024)黔0526民初10454号", 3714.08, "贵州省威宁彝族回族苗族自治县人民法院", "一审判决支付工程款2,874.09万元及利息、质保金444.46万元及利息，七建公司享有优先受偿权；被告已履行完毕。", [2]),
    ("P", 5, "重庆建工市政交通工程有限责任公司", "重庆迈瑞城市建设投资有限责任公司、重庆丰文实业有限公司", "建设工程合同纠纷", "(2024)渝0106民初3454号", 8677.26, "重庆市沙坪坝区人民法院", "一审判决支付工程款6,337.79万元及利息；被告已履行完毕。", [2]),
    ("P", 6, "重庆建工市政交通工程有限责任公司", "重庆市武隆区建设投资（集团）有限公司", "建设工程施工合同纠纷", "(2025)渝0156民初696号", 1519.27, "重庆市武隆区人民法院", "一审判决支付工程款680.58万元及利息；被告已履行完毕。", [2, 3]),
    ("P", 7, "重庆建工", "重庆腾希置业发展有限公司", "建设工程合同纠纷", "(2024)渝0118民初1537号", 9480.35, "重庆市永川区人民法院、重庆市第五中级人民法院", "一审判决工程款7,433.64万元及资金占用损失并确认优先受偿权；二审工程款改为5,758.31万元及资金占用损失，优先受偿权保留；判决已履行完毕。", [3]),
    ("P", 8, "重庆工业设备安装集团有限公司", "四川煤气化有限责任公司", "建设工程施工合同纠纷", "(2019)川05民初59号", 5963.62, "四川省泸州市中级人民法院", "一审判决工程款5,878.82万元、保证金80.00万元及利息，确认优先受偿权；债务人破产，原告分配两笔共2,856.23万元后公司注销，本案结案。", [3]),
    ("P", 9, "重庆建工工业有限公司", "龚节华", "建设工程合同纠纷", "(2023)渝0116民初10045号", 4414.41, "重庆市江津区人民法院、重庆市第五中级人民法院、重庆市高级人民法院", "一审驳回原告诉请，二审维持，再审申请被驳回；判决生效、结案。", [3]),
    ("P", 10, "重庆建工住宅建设有限公司", "遵义市永和城置业有限公司", "建设工程施工合同纠纷", "(2024)黔03民初177-1号", 13638.10, "贵州省遵义市中级人民法院、贵州省高级人民法院", "重审期间被告进入破产重整，原告确认优先债权11,686.18万元，少量债权仍在确认；原告已撤诉。", [3]),
    ("P", 11, "重庆建工第八建设有限责任公司", "张洋", "合同纠纷", "(2017)渝0107民初19887号", 1298.78, "重庆市九龙坡区人民法院", "一审判决返还代付款1,126.60万元及利息；判决生效，案件履行中。", [3]),
    ("P", 12, "重庆建工第二建设有限公司", "重庆富州房地产开发有限公司、上海宏铭企业发展有限公司、林金清、陈才义（第三人）、重庆建渝工程咨询有限公司（第三人）", "建设工程合同纠纷", "(2024)渝0106民初22758号", 3894.10, "重庆市沙坪坝区人民法院、重庆市第一中级人民法院", "一审判工程进度款2,084.32万元及暂计利息76.93万元、返还履约保证金218.45万元及利息损失，享有优先受偿权并驳回反诉；二审调解确认支付工程款3,997.21万元，调解生效、履行中。公告表格另列5,095.08万元，性质须核对原件。", [3, 4]),
    ("P", 13, "重庆建工", "重庆两江新区新榈实业有限公司", "建设工程合同纠纷", "(2025)渝0112民初64333号", 3255.91, "重庆市两江新区人民法院、重庆市第一中级人民法院", "一审判工程款1,023.28万元，二审维持；判决生效、履行中。", [4]),
    ("P", 14, "郑俊亮", "阿勒泰卓渝建筑工程有限责任公司青海分公司、阿勒泰卓渝建筑工程有限责任公司", "合同纠纷", "(2025)青0104民初8548号", 6567.27, "青海省西宁市城西区人民法院", "一审判工程款6,107.02万元；被告已上诉，二审审理中。公告所列原告为郑俊亮，重庆建工并非当事人。", [4]),
    ("P", 15, "阿勒泰卓渝建筑工程有限责任公司", "重庆三峡继成置业有限公司", "建设工程施工合同纠纷", "(2025)渝0106民初11844号", 13386.29, "重庆市沙坪坝区人民法院", "一审判工程款10,608.06万元及利息、返还履约保证金1,000.00万元及利息损失，并确认优先受偿权；判决生效、履行中。", [4]),
    ("P", 16, "重庆建工第二建设有限公司", "兰州南河道生态文化旅游开发有限公司、兰州市城关区城市发展投资（集团）有限公司", "保证金纠纷", "(2025)渝0106民初54423号；(2026)甘01民初44号", 58164.15, "重庆市沙坪坝区人民法院、甘肃省兰州市中级人民法院", "原告变更诉求；案件从重庆市沙坪坝区人民法院移送兰州市中级人民法院审理。", [4]),
    ("P", 17, "重庆建工第十一建筑工程有限责任公司", "重庆鹏博实业有限公司、重庆瑞安物业发展有限公司、重庆市疾病预防控制中心", "建设工程施工合同纠纷", "(2025)渝0105民初33130号", 24043.97, "重庆市江北区人民法院、重庆市两江新区人民法院", "一审判解除合同，两公司支付工程款17,598.97万元及利息并确认优先受偿权；判决生效、履行中。", [4]),
    ("P", 18, "西藏渝昌建设有限责任公司（原名：重庆建工第四建设有限责任公司）", "重庆交运物流有限公司", "建设工程施工合同纠纷", "(2024)渝0106民初27463号", 1677.17, "重庆市沙坪坝区人民法院", "原告变更诉请；一审判支付工程款1,144.19万元及利息并确认优先受偿权；双方均上诉，二审中。", [4]),
    ("P", 19, "重庆建工住宅建设有限公司", "旺苍县中瑞诚房地产开发有限责任公司、宋增军、杨洋、税国全、王宇、吴晓山、邓坤、税正玉", "建设工程施工合同纠纷", "(2025)川0821民初2786号", 6478.03, "四川省旺苍县法院", "一审判工程进度款351.91万元、暂计资金占用费361.65万元及履约保证金资金占用费100.13万元，列明多名连带责任人并确认优先受偿权；原告已上诉，二审中。", [4, 5]),
]


def locate_pdf(input_dir):
    files = list(Path(input_dir).glob("*.pdf"))
    if len(files) != 1:
        raise RuntimeError(f"Expected exactly one source PDF, found {len(files)}")
    return files[0]


def page_texts(pdf_path):
    reader = PdfReader(str(pdf_path))
    return [p.extract_text() or "" for p in reader.pages]


def page_money_occurrences(text):
    return [float(x.replace(",", "")) for x in re.findall(r"(?<!\d)(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}(?!\d)", text)]


def build_records(pdf_path):
    pages = page_texts(pdf_path)
    records = []
    for group, number, plaintiff, defendant, cause, case_no, amount, court, progress, page_nums in CASE_META:
        prefix = "N" if group == "N" else "P"
        code = f"ANN-20260822-{prefix}{number:02d}"
        records.append({"code": code, "group": "本次新案" if group == "N" else "前期披露案件", "number": number,
                        "plaintiff": plaintiff, "defendant": defendant, "cause": cause, "case_no": case_no,
                        "amount": amount, "court": court, "progress": progress, "pages": page_nums,
                        "role": "发行人公告摘要；案情/程序为公告转述，未经原始卷宗独立核验",
                        "verification": "与公告原件页码核对；底层事实待调卷核验"})
    # A cross-page table row has content on both pages; page provenance is retained.
    for r in records:
        if r["code"] == "ANN-20260822-P06":
            r["case_no"] = "(2025)渝0156民初696号"
        if r["code"] == "ANN-20260822-P12":
            r["progress"] += "公告第3页另列5,095.08万元子行，公告将其列在重庆富州房地产开发有限公司一侧；该金额与案件金额及二审调解金额口径不同，须核对来源文件。"
    return records, pages


def style_sheet(ws):
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="245B55")
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    ws.row_dimensions[1].height = 34
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")


def create_workbook(path, source_name, records):
    wb = Workbook()
    idx = wb.active
    idx.title = "材料索引"
    idx.append(["内部整理码", "材料名称", "材料类型", "来源/身份", "披露日期", "页数", "用途及限制", "核验状态"])
    idx.append(["SRC-01", source_name, "PDF公告原件", "重庆建工集团股份有限公司，公告编号临2026-043", "2026-08-22", 5,
                "用于登记公告转述的案件身份、金额、法院和进展；不能替代原始证据或裁判文书", "文件哈希与资源库原件一致"])
    style_sheet(idx)
    idx.column_dimensions["A"].width = 16
    idx.column_dimensions["B"].width = 46
    for col in "CDEFGH": idx.column_dimensions[col].width = 26

    ws = wb.create_sheet("案件登记")
    headers = ["内部整理码", "公告分组", "公告序号", "原告（公告）", "被告（公告）", "案由（公告）", "案号（公告）", "涉案金额（万元）", "受理法院（公告）", "公告所述进展", "公告页码", "程序事件日", "事实角色", "核验状态", "提交编号"]
    ws.append(headers)
    for r in records:
        ws.append([r["code"], r["group"], r["number"], r["plaintiff"], r["defendant"], r["cause"], r["case_no"], r["amount"], r["court"], r["progress"], ", ".join(map(str, r["pages"])), None, r["role"], r["verification"], f"{'N' if r['group']=='本次新案' else 'P'}{r['number']:02d}"])
    style_sheet(ws)
    widths = [24, 16, 12, 33, 52, 24, 35, 18, 36, 76, 16, 18, 48, 40, 20]
    for i, width in enumerate(widths, 1): ws.column_dimensions[chr(64+i)].width = width
    ws.auto_filter.ref = f"A1:O{len(records)+1}"
    tab = Table(displayName="CaseRegister", ref=f"A1:O{len(records)+1}")
    tab.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True, showColumnStripes=False)
    ws.add_table(tab)
    for row in range(2, len(records)+2): ws.cell(row, 8).number_format = '#,##0.00'

    sm = wb.create_sheet("金额汇总")
    sm.append(["项目", "公式/金额（万元）", "取值口径", "来源"])
    sm.append(["新发生4案涉案金额合计", "=SUM('案件登记'!H2:H5)", "公告列示涉案金额之和，不代表判决或未偿金额", "公告第1-2页"])
    sm.append(["前期19案涉案金额合计", "=SUM('案件登记'!H6:H24)", "公告列示涉案金额之和，不代表判决或未偿金额", "公告第2-5页"])
    sm.append(["新案+前期披露案件合计", "=SUM(B2:B3)", "仅为上述23项公告涉案金额合计", "上述两项"])
    sm.append(["公告所述2026年度利润影响", 204.62, "已结案件增加利润；未经审计确认", "公告第5页"])
    sm.append(["新案数", "=COUNTA('案件登记'!A2:A5)", "公告第一部分", "公告第1-2页"])
    sm.append(["前期案件数", "=COUNTA('案件登记'!A6:A24)", "公告第二部分", "公告第2-5页"])
    style_sheet(sm)
    for c,w in {"A":38,"B":24,"C":64,"D":22}.items(): sm.column_dimensions[c].width=w
    for row in range(2,6): sm.cell(row,2).number_format = '#,##0.00'
    sm["B5"].number_format = '#,##0.00'

    supp = wb.create_sheet("补件台账")
    supp.append(["编号", "范围/案件", "待调取材料", "核验事项", "优先级", "当前状态"])
    asks = [
        ("ALL-01", "共性/全部案件", "完整起诉状、答辩状、反诉状及诉请变更申请", "逐项核实诉辩立场、请求金额、反请求及争议事实", "高", "公告不含，待调取"),
        ("ALL-02", "共性/建设工程案件", "施工合同、补充协议、招投标文件及计价附件", "核对主体、承包范围、价款、付款条件和合同相对方", "高", "公告不含，待调取"),
        ("ALL-03", "共性/工程价款案件", "付款流水、发票、对账及收款凭证", "核验已付款、欠款余额、款项用途与公告金额差异", "高", "公告不含，待调取"),
        ("ALL-04", "共性/工程履行案件", "开竣工、施工日志、签证、变更、验收、结算资料", "核实履行范围、工期节点、质量、结算与价款形成", "高", "公告不含，待调取"),
        ("ALL-05", "共性/催告及保修金", "催款通知、送达凭证、质保金约定与保修记录", "核对催告事实、送达、质保金条件和保修义务", "中", "公告不含，待调取"),
        ("ALL-06", "共性/程序", "法院受理、举证通知、庭审笔录、裁定、判决、调解书及送达凭证", "核实程序阶段、裁判主文、上诉/移送/生效/履行状态", "高", "公告转述，待原件核对"),
        ("P12", "ANN-20260822-P12", "第3页5,095.08万元表格子行对应的原始诉辩/反诉材料及金额计算表", "确定该金额的主张主体、性质、是否反诉及其与3,894.10万元、3,997.21万元的关系", "高", "公告版面存在，实质待核"),
        ("P16", "ANN-20260822-P16", "移送裁定、变更诉请文件及兰州中院受理材料", "核对移送时间、新案号与变更后的请求", "高", "公告未载具体事件日"),
        ("P14", "ANN-20260822-P14", "案件委托/关联范围确认及郑俊亮案件诉辩、裁判材料", "确认该项纳入整理范围的业务关联，不将郑俊亮表述为重庆建工", "中", "公告主体已标识"),
        ("ALL-07", "共性/庭前提交", "法院要求提交的证据副本、原件核对清单及送达回证", "建立原件状态、页码、提交编号与卷宗位置映射", "高", "举证通知未提供"),
    ]
    for row in asks: supp.append(row)
    style_sheet(supp)
    for i,w in enumerate([15,30,58,68,14,28],1): supp.column_dimensions[chr(64+i)].width=w
    supp.auto_filter.ref = f"A1:F{len(asks)+1}"

    wb.calculation.fullCalcOnLoad = True
    wb.calculation.forceFullCalc = True
    wb.calculation.calcMode = "auto"
    wb.save(path)


def register_fonts():
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    from reportlab.lib.fonts import addMapping
    addMapping("STSong-Light", 0, 0, "STSong-Light")


def styles():
    register_fonts()
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("CNTitle", parent=base["Title"], fontName="STSong-Light", fontSize=17, leading=23, alignment=TA_CENTER, textColor=colors.HexColor("#174F4A"), spaceAfter=9),
        "h": ParagraphStyle("CNH", parent=base["Heading2"], fontName="STSong-Light", fontSize=12, leading=16, textColor=colors.HexColor("#174F4A"), spaceBefore=7, spaceAfter=5),
        "body": ParagraphStyle("CNBody", parent=base["BodyText"], fontName="STSong-Light", fontSize=8.3, leading=12, spaceAfter=4),
        "small": ParagraphStyle("CNSmall", parent=base["BodyText"], fontName="STSong-Light", fontSize=7.2, leading=10),
        "cell": ParagraphStyle("CNCell", parent=base["BodyText"], fontName="STSong-Light", fontSize=7, leading=9),
    }


def para(text, style):
    return Paragraph(escape(str(text)).replace("\n", "<br/>"), style)


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("STSong-Light", 8)
    canvas.setFillColor(colors.HexColor("#58615F"))
    canvas.drawString(15*mm, 10*mm, "工作底稿 | 公开披露线索，不替代案件原始证据")
    canvas.drawRightString(doc.pagesize[0]-15*mm, 10*mm, f"第 {doc.page} 页")
    canvas.restoreState()


def make_catalog(path, source_name, records):
    s = styles()
    doc = SimpleDocTemplate(str(path), pagesize=landscape(A4), rightMargin=12*mm, leftMargin=12*mm, topMargin=13*mm, bottomMargin=16*mm, title="证据目录")
    story = [para("证据目录：诉讼公告线索", s["title"]),
             para(f"文件：{source_name}。来源：重庆建工集团股份有限公司公告（2026年8月22日，临2026-043），共5页。以下条目为公告所载案件线索，不是合同、诉辩证据或法院裁判原件。金额为公告涉案金额（万元），不可直接理解为判决金额或未偿金额。", s["body"]), Spacer(1, 3*mm)]
    data = [[para(x,s["cell"]) for x in ["提交编号 / 内部整理码", "案号", "原告 / 被告", "案由", "页码", "公告所述证明范围"]]]
    for r in records:
        summary = f"涉案金额 {r['amount']:,.2f} 万元；{r['progress']} 事实及程序均为发行人公告转述，待原件核实。"
        data.append([para(f"{('N' if r['group']=='本次新案' else 'P')}{r['number']:02d}<br/>{r['code']}",s["cell"]),para(r["case_no"],s["cell"]),para(f"原告：{r['plaintiff']}<br/>被告：{r['defendant']}",s["cell"]),para(r["cause"],s["cell"]),para(", ".join(map(str,r["pages"])),s["cell"]),para(summary,s["cell"])])
    t = LongTable(data, colWidths=[37*mm,37*mm,77*mm,35*mm,16*mm,73*mm], repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#245B55")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),0.35,colors.HexColor("#AAB7B4")),("VALIGN",(0,0),(-1,-1),"TOP"),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#F1F5F3")]),("LEFTPADDING",(0,0),(-1,-1),4),("RIGHTPADDING",(0,0),(-1,-1),4),("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4)]))
    story.append(t)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)


def make_supplement(path):
    s=styles()
    doc=SimpleDocTemplate(str(path),pagesize=A4,rightMargin=17*mm,leftMargin=17*mm,topMargin=15*mm,bottomMargin=17*mm,title="补充材料与核查清单")
    story=[para("补充材料与核查清单",s["title"]),para("基准材料仅为2026年8月22日上市公司诉讼公告。公告摘要可以提供案件识别线索，但不支持对合同履行、欠款余额、证据真实性或裁判原文作独立确认。以下事项应结合实际委托范围逐案核实。",s["body"])]
    items=[
        ("一、先确认案件范围与程序状态",["逐案取得完整起诉状、答辩状、反诉状及历次诉请变更文件，核对请求主体、请求金额、抗辩和反请求；P12公告列示5,095.08万元的子行须回查其原始表格及对应诉辩材料。","取得法院受理通知、举证通知、庭审笔录、裁定、判决、调解书及送达回证；核实公告所述上诉、移送、撤诉、生效、履行或结案情况及其具体日期。","P14公告列示原告为郑俊亮，先确认是否属于本次委托整理范围；不得将其写成重庆建工或其子公司。P16核实渝、甘两地案号衔接和移送后请求。"]),
        ("二、工程价款事实链",["调取施工合同、补充协议、招投标文件、工程量清单和计价附件，核对签约主体、承包范围、计价方式、付款节点、结算及争议解决条款。","调取开竣工资料、施工日志、签证变更、工程量确认、验收/移交、停复工及质量维修材料，逐项核实实际履行范围和日期。","调取结算书、审价/对账、发票、付款流水、收款凭证和资金往来，拆分工程款、保证金、利息、资金占用损失及已付款，复核公告数字与当前余额。"]),
        ("三、催告、质量及担保材料",["调取催款通知、送达凭证、往来函件、会议纪要与对账确认，核实通知内容、收件主体、日期及对方回复。","调取质量保证金约定、保修期起算资料、缺陷通知、维修记录和扣款依据，核实保证金返还条件及金额。","存在保证、连带责任或第三人时，取得相应承诺、授权、合同与诉讼材料，核对其身份和责任范围。"]),
        ("四、优先补件案件",["P06：原公告表格跨第2-3页，案号续行为初696号；取得原件核对案号、被告全称及判决/履行状态。","P12：公告表格出现5,095.08万元子行，须确认金额性质、主张主体及其与一审请求和二审调解金额的勾稽关系；不据公告版式推定其为法院认定。","P16：取得诉请变更材料、移送裁定及兰州中院受理文书，确认变更后诉请和程序时间线。","P19：取得二审上诉状、受理材料及一审裁判，核实金额分项、连带责任主体和优先受偿权内容。"]),
        ("五、整理与提交控制",["确认法院举证期限、证据交换要求和提交格式；取得待提交证据原件/原始载体，逐件登记形成时间、来源、原件状态、页码和保管人。","建立内部整理码与最终提交编号映射，检查重复、缺页、附件、引用定位及原件核对安排。公告披露日期不是具体案件事件日期；未知日期留空，后续以原件补齐。"]),
    ]
    for title, bullets in items:
        story.append(para(title,s["h"]))
        for b in bullets: story.append(para("• "+b,s["body"]))
    story.append(Spacer(1,4*mm))
    story.append(para("工作边界：本清单用于安排材料调取和事实核验，不对各案实体请求、证据证明力或裁判结果作结论。",s["body"]))
    doc.build(story,onFirstPage=footer,onLaterPages=footer)


def recalc_workbook(path, output_dir):
    profile=Path(output_dir)/".lo-profile"
    profile.mkdir(parents=True,exist_ok=True)
    cmd=["libreoffice", "-env:UserInstallation="+profile.as_uri(), "--headless", "--convert-to", "xlsx", "--outdir", str(Path(output_dir)), str(path)]
    # Convert-to on the same extension is not portable; use a temporary directory and replace after recalculation.
    tmp=Path(output_dir)/".recalc"
    tmp.mkdir(exist_ok=True)
    cmd=["libreoffice","-env:UserInstallation="+profile.as_uri(),"--headless","--convert-to","xlsx","--outdir",str(tmp),str(path)]
    proc=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=120)
    candidate=tmp/Path(path).name
    if proc.returncode==0 and candidate.exists():
        os.replace(candidate,path)
    else:
        # Calc may refuse same-format conversion; opening/saving via a macro is unnecessary because formulas recalc on open.
        data=load_workbook(path,data_only=False)
        data.calculation.fullCalcOnLoad=True
        data.calculation.forceFullCalc=True
        data.calculation.calcMode="auto"
        data.save(path)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input-data",required=True)
    ap.add_argument("--output",required=True)
    args=ap.parse_args()
    input_dir=Path(args.input_data); out=Path(args.output); out.mkdir(parents=True,exist_ok=True)
    source=locate_pdf(input_dir)
    records,_=build_records(source)
    create_workbook(out/"evidence_workbook.xlsx",source.name,records)
    recalc_workbook(out/"evidence_workbook.xlsx",out)
    make_catalog(out/"evidence_catalog.pdf",source.name,records)
    make_supplement(out/"supplementation_note.pdf")

if __name__=="__main__":
    main()
