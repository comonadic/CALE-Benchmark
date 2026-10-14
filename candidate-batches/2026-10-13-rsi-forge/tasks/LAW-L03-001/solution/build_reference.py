#!/usr/bin/env python3
import argparse
import html
import re
import subprocess
import tempfile
from pathlib import Path

import fitz
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

DOCS = {
    "CN-1225327554.pdf": "2026年5月重组报告书（草案）",
    "CN-1225327559.pdf": "2026年5月法律意见书（扫描件）",
    "CN-1225327560.pdf": "天健审〔2026〕8-580号审计报告",
    "CN-1225449371.pdf": "2026-072号修订说明公告",
    "CN-1225449382.pdf": "2026年7月补充法律意见书（一）（扫描件）",
    "CN-1225449388.pdf": "2026年7月重组报告书（草案）（修订稿）",
    "CN-1225449390.pdf": "天健审〔2026〕8-650号审计报告",
}

# Rows are project requests derived from the transaction's disclosed scope and
# document gaps. Source-dependent claims are marked as disclosure, not findings.
ROWS = [
    ("R01", "交易主体、标的及40%股权交易范围", "交易方案、股权转让协议及主体资格文件；本轮交易", "CN-1225449388.pdf，第1章交易概况", "披露称收购中信信托代表信华57号持有的国城实业40%股权；本轮为公开披露线索，未见签署版协议。", "部分覆盖", "交易主体及比例来自修订稿披露，尚未以协议及股东名册核实。", "提供签署版股权转让协议、信托计划授权及交割前后股权结构/股东名册。", "优先补齐交易协议和股权登记材料。"),
    ("R02", "2026年5月草案与7月修订稿的版本关系", "两版报告书及修订对照/定稿记录", "CN-1225327554.pdf；CN-1225449388.pdf；CN-1225449371.pdf", "7月修订稿对应5月草案；2026-072公告说明因加期财务数据及问询核查等对披露文件修订、补充。", "已覆盖", "版本关系和公告修订范围可由公开文件识别；未取得逐页修订对照及内部定稿记录。", "提供中介机构修订对照表及最终披露版本确认记录。", "将旧版保留为历史版本，不作为当前数据口径。"),
    ("R03", "评估基准日与40%股权交易价款", "评估报告、交易协议；基准日2025-12-31", "CN-1225449388.pdf，第1章交易概况", "修订稿披露评估基准日为2025-12-31，100%股权评估值600,270.54万元；考虑补缴情形及分红后40%对应价值592,070.01万元，协商交易价236,800.00万元。", "部分覆盖", "金额及口径为报告书披露，未见完整评估报告、评估说明及签署协议。", "提供评估报告全本、评估基准日至定价日调整依据及签署版交易协议。", "复核估值调整与协议价款是否一致。"),
    ("R04", "8-580号审计期间", "审计报告全本；2024、2025年度", "CN-1225327560.pdf", "天健审〔2026〕8-580号审计报告覆盖2024-01-01至2025-12-31，资产负债表日为2024-12-31及2025-12-31。", "已覆盖", "审计报告期间可从报告正文读取；该版本不含2026年1-4月。", "如用于当前交易财务口径，提供加期后的审计报告并确认旧版留档用途。", "标注为历史审计版本，勿用于替代加期报告。"),
    ("R05", "8-650号新增审计基准及期间", "加期审计报告全本；截至2026-04-30", "CN-1225449390.pdf", "天健审〔2026〕8-650号覆盖2024年度、2025年度及2026年1-4月，资产负债表增加2026-04-30。", "已覆盖", "期间由审计报告正文支持；仍需核验签章及附件完整性。", "确认签章原件/电子签章验证信息及交付版本完整。", "以加期版本更新本轮财务需求状态。"),
    ("R06", "2026-072修订说明所述更新事项", "公告原件及修订后报告书", "CN-1225449371.pdf；CN-1225449388.pdf", "公告列明更新加期财务数据、交易程序、减持情况、采矿权抵押、对外担保、行政处罚、关联交易等修订事项。", "已覆盖", "修订说明仅概述披露修订主题，不等于支持其底层事实的原始证据。", "按事项取得相关原件及中介核查底稿/确认记录。", "逐项将修订事项映射到相应底层证据需求。"),
    ("R07", "2026年5月法律意见书身份与可读性", "法律意见书全本及可检索版本；2026年5月", "CN-1225327559.pdf（扫描件）", "文件为北京中银律师事务所关于本次重大资产购买暨关联交易之法律意见书；该 PDF 为扫描件，机器文本层不可用。", "部分覆盖", "可识别文件身份，正文细节需页面渲染核查；意见书结论不能替代底层证据。", "提供可检索电子版或清晰签章原件，并索取其事实依据清单。", "扫描材料按页核对并记录页码。"),
    ("R08", "2026年7月补充法律意见书（一）", "补充法律意见书全本及事实核查底稿；2026年7月", "CN-1225449382.pdf（扫描件）", "文件为北京中银律师事务所补充法律意见书（一）；该 PDF 为扫描件，机器文本层不可用。", "部分覆盖", "能识别文件身份与版本，具体补充事项须人工核读；不等同本项目完整尽调底稿。", "提供可检索版、完整签章件及对应核查底稿/附件。", "与5月法律意见书一并标注版本及补充范围。"),
    ("R09", "采矿权及探矿权", "采矿许可证、探矿许可证、矿业权档案及缴费凭证；现行有效版本", "CN-1225449388.pdf，标的公司业务/矿业权章节", "报告书披露国城实业持有采矿权、探矿权，并陈述证照及权属情况；本轮未提供许可证原件。", "部分覆盖", "公开披露只能作为需核验线索，不能核验许可证有效期、范围和登记状态。", "提供全部许可证正副本、登记查询、年检/缴费凭证及矿业权档案。", "列为高优先级权属与许可补件。"),
    ("R10", "采矿权扩界扩能变更", "变更申请、受理/审批材料及新证；当前办理状态", "CN-1225449388.pdf，风险因素及矿业权章节", "报告书披露拟将生产规模由500万吨/年扩大至800万吨/年，采矿权变更手续仍在办理。", "部分覆盖", "披露显示手续未完成；不得将拟扩能视为已取得许可。", "提供申请文件、主管部门受理/补正/审批文件、预计时间及当前有效采矿许可证。", "交割/估值条件分析前确认审批进度与未获批后果。"),
    ("R11", "采矿权抵押及清偿", "抵押合同、矿业权抵押备案/变更/注销证明及清偿凭证", "CN-1225449388.pdf，采矿权抵押情况", "修订稿披露采矿权存在抵押，并称截至报告书签署日以中信信托为抵押权人的相关贷款已提前清偿完毕。", "部分覆盖", "披露了抵押和清偿线索；未见抵押登记注销或债权人确认原件。", "逐笔提供抵押合同、登记证明、清偿凭证、抵押权人解除确认及登记注销查询。", "核实抵押权是否已实际注销及其他抵押是否持续。"),
    ("R12", "标的40%股权质押及冻结", "股东名册、市场监管登记/司法查询及信托权属文件；截至交割前", "CN-1225449388.pdf，交易标的权属", "修订稿披露截至签署日交易标的40%股权不存在质押及冻结。", "部分覆盖", "为报告书陈述，未附本轮独立查询结果或最新交割前状态证明。", "提供最新股东名册、登记档案、司法冻结查询及信托计划持有证明。", "交割前更新查询并将时点写入台账。"),
    ("R13", "报告期行政处罚", "处罚决定书、缴款/整改材料及主管机关证明；报告期内", "CN-1225449388.pdf，行政处罚及合规章节", "修订稿披露报告期以来标的公司受到行政处罚共7起，并作相关影响说明。", "部分覆盖", "处罚数量及说明来自披露文件；本轮未提供7起处罚决定书及整改闭环证据。", "逐项提供决定书、履行凭证、整改验收/复查材料及未结事项确认。", "建立逐案子清单，区分处罚主体、日期、金额、整改状态。"),
    ("R14", "关联交易及底层依据", "关联方清单、关联交易合同、定价依据、决策和结算凭证；报告期", "CN-1225449388.pdf，第十章关联交易", "修订稿设有报告期关联方及关联交易披露；本轮未包含合同、定价及结算底层文件。", "部分覆盖", "披露章节可作为事项目录，不足以核对交易完整性、公允性及审批。", "提供关联方清单、逐项合同/订单、定价依据、决议、发票和结算记录。", "以关联方主数据与账簿/合同抽样勾稽。"),
    ("R15", "交易决策及报批程序", "董事会决议、交易对方/控股股东决策、股东会及其他审批文件", "CN-1225449388.pdf，交易程序章节", "修订稿区分已履行的上市公司董事会及相关主体内部决策，与尚需上市公司股东会审议及其他依法需履行程序。", "部分覆盖", "公开披露提供程序状态陈述；未见决议原件或全部审批文件。", "提供董事会/股东会决议、通知与表决记录、交易对方授权及审批/备案清单。", "将尚需程序作为未完成事项跟踪，不写成已获批准。"),
    ("R16", "签署版交易协议及交割条件", "股权收购协议、补充协议、交割清单和先决条件证明", "CN-1225449388.pdf，交易方案披露", "报告书披露交易方案及交易价格，但本轮输入不含签署版交易协议及交割条件附件。", "未提供", "披露摘要无法替代合同条款，现阶段不能核实生效、付款、先决条件及违约安排。", "提供各方签署版协议、补充协议、交割条件清单及已满足条件证明。", "在取得协议前将合同审查保持待办。"),
    ("R17", "业绩承诺及补偿保障", "业绩承诺/补偿协议、保障承诺原件及履行担保文件", "CN-1225449388.pdf，交易方案及承诺章节；CN-1225449371.pdf", "修订稿及修订说明提及业绩承诺、补偿安排及相关保障措施；本轮未提供承诺原件和担保文件。", "部分覆盖", "披露说明可识别文件需求，不足以确认承诺人、计算口径、保障效力和可执行性。", "提供签署文件、承诺主体授权、担保/质押登记及补偿测算附件。", "按承诺期间、口径、触发和保障逐条核验。"),
    ("R18", "审计报告签章与资质附件", "8-650审计报告签章件、注册会计师资质及完整附件", "CN-1225449390.pdf", "本轮收到加期审计报告 PDF；报告目录显示包含财务报表、附注及资质附件。", "部分覆盖", "PDF 可见不代表电子签章、执业资质或原始文件完整性已独立验证。", "提供原始签章文件/验签信息、报告防伪查询及附件完整性确认。", "核验签章、报告编号和附件页数后再将审计资料标为完整。"),
    ("R19", "目标公司主体档案", "营业执照、章程及历次工商档案；当前及历次变更", "本轮未提供目标公司主体档案；公开报告书仅有披露信息", "材料目录不含国城实业营业执照、现行章程和完整历史沿革档案。", "未提供", "报告书的主体介绍不能替代登记档案及现行有效章程。", "提供营业执照、现行章程、历次章程修正案、工商内档及登记查询。", "与签署协议主体和授权链核对。"),
    ("R20", "股权结构、股东名册及出资", "完整股东名册、出资证明/流水、历次股权变动协议", "CN-1225449388.pdf可提供公开股权线索；底层材料未提供", "公开披露描述交易对方及标的股权，但本轮没有股东名册、出资凭证及完整变动档案。", "部分覆盖", "公开股权描述不构成对历史出资、代持或权利限制的独立核查。", "提供设立至今股权变动协议、出资凭证、股东名册、代持/争议确认及登记档案。", "重点核实40%股权权属链和授权。"),
    ("R21", "重大合同与履行/违约", "重大采购、销售、融资、担保及关联合同；报告期及未履行合同", "本轮报告书有合同事项披露线索；合同原件未提供", "公开报告书可提示融资、担保及经营合同事项，但未提供完整重大合同目录和合同原件。", "未提供", "不能由公开披露中出现的合同线索推定合同集合完整。", "提供完整合同台账、重大合同及补充协议、履行/违约/终止通知和债务余额确认。", "按金额、期限、控制权变更及违约条款筛查。"),
    ("R22", "主要资产权属、土地房产及在建工程", "土地/房产权证、设备清单、在建工程合同及抵押查册；当前", "CN-1225449388.pdf披露部分资产/土地/设备事项；原件未提供", "修订说明提及补充土地证号、机器设备及更新担保信息；未附权证、登记查询和完整资产底册。", "部分覆盖", "披露目录线索不证明权证有效、资产完整或不存在其他权利负担。", "提供资产清单及抽盘/账证勾稽、土地房产权证、设备权属、在建工程合同和抵押查册。", "结合抵押及扩能项目核查资产权属和许可。"),
    ("R23", "劳动用工、社保及争议", "员工名册、劳动合同、社保缴纳和劳动争议清单；截至本轮", "本轮未提供劳动人事底层材料", "未见员工名册、劳动合同、社保缴费凭证或劳动争议全量清单。", "未提供", "公开交易文件未列示相关细节不能推定不存在劳动风险。", "提供按主体/用工类型汇总的员工名册、劳动合同样本及重大人员清单、社保缴费凭证、争议台账。", "关注矿山生产外包与劳务用工边界。"),
    ("R24", "上轮需求、数据室索引及逐项回复", "上轮需求清单、数据室原始索引、上传时间/版本和逐项答复", "本轮未提供；CN-1225449371.pdf仅为公开修订说明", "未提供真实上轮清单、数据室索引、上传时间记录或目标公司逐项回复；公开修订说明不是数据室回复。", "未提供", "缺少基线，无法认定本轮新增/关闭了哪些需求，也无法核对数据室覆盖率。", "提供带路径、上传时间、版本及回复人的原始索引和上轮清单/回复记录。", "收到后建立快照并保留需求历史，不覆盖历史状态。"),
]


def extract_text(input_dir: Path):
    docs = {}
    for name in DOCS:
        p = input_dir / name
        if not p.is_file() or p.stat().st_size == 0:
            raise RuntimeError(f"missing or empty trusted input: {name}")
        doc = fitz.open(p)
        docs[name] = "\n".join(page.get_text() for page in doc)
    if "236,800.00" not in docs["CN-1225449388.pdf"]:
        raise RuntimeError("revised report text extraction failed its transaction-price anchor")
    normalized_650 = re.sub(r"\s+", "", docs["CN-1225449390.pdf"])
    normalized_580 = re.sub(r"\s+", "", docs["CN-1225327560.pdf"])
    if "2026年4月30日" not in normalized_650 or "2026年1-4月" not in normalized_650:
        raise RuntimeError("8-650 audit period anchor missing")
    if "2025年12月31日" not in normalized_580 or "2026年1-4月" in normalized_580:
        raise RuntimeError("8-580 audit period anchor missing")
    return docs


def style_workbook(path: Path):
    wb = Workbook()
    ws = wb.active
    ws.title = "需求跟踪"
    headers = ["需求编号", "调查事项", "所需文件/期间/版本", "材料对应", "文件日期/期间", "覆盖状态", "状态依据与限制", "追问/补件", "跟进动作"]
    ws.append(headers)
    for row in ROWS:
        ws.append(list(row))
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    widths = [12, 30, 37, 38, 30, 14, 54, 54, 42]
    for idx, width in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(idx)].width = width
    for cell in ws[1]:
        cell.font = Font(name="Noto Sans CJK SC", bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="245B55")
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    ws.row_dimensions[1].height = 32
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.font = Font(name="Noto Sans CJK SC", size=10)
            cell.alignment = Alignment(wrap_text=True, vertical="top")
        row[0].font = Font(name="Noto Sans CJK SC", bold=True, color="245B55")
        row[5].fill = PatternFill("solid", fgColor={"已覆盖":"DDEFE9", "部分覆盖":"FFF0CB", "未提供":"FCE2DE", "不适用":"E7E7E7"}.get(row[5].value, "FFFFFF"))
        ws.row_dimensions[row[0].row].height = 86
    ver = wb.create_sheet("口径与版本")
    ver.append(["文件名", "文件身份", "文件日期", "版本关系/适用期间", "核对限制"])
    version_rows = [
        ("CN-1225327554.pdf", DOCS["CN-1225327554.pdf"], "2026-05", "初始草案；本轮交易披露", "报告书披露，不替代交易原件"),
        ("CN-1225449388.pdf", DOCS["CN-1225449388.pdf"], "2026-07", "CN-1225327554.pdf修订稿；报告期截至2026-04-30", "以修订稿作为本轮披露口径"),
        ("CN-1225327560.pdf", DOCS["CN-1225327560.pdf"], "2026-05-19", "8-580；2024及2025年度/年末", "不含2026年1-4月"),
        ("CN-1225449390.pdf", DOCS["CN-1225449390.pdf"], "2026-07-10", "8-650；2024、2025年度及2026年1-4月", "加期版本；需核验签章与完整性"),
        ("CN-1225327559.pdf", DOCS["CN-1225327559.pdf"], "2026-05", "本交易法律意见书", "扫描件，需页面核读"),
        ("CN-1225449382.pdf", DOCS["CN-1225449382.pdf"], "2026-07", "前述意见书的补充法律意见（一）", "扫描件，需页面核读"),
        ("CN-1225449371.pdf", DOCS["CN-1225449371.pdf"], "2026-07-30", "2026-072修订说明公告", "事项索引，不是底层核查材料"),
    ]
    for row in version_rows:
        ver.append(row)
    ver.freeze_panes = "A2"
    ver.auto_filter.ref = ver.dimensions
    for idx, width in enumerate([25, 48, 18, 49, 45], 1):
        ver.column_dimensions[get_column_letter(idx)].width = width
    for cell in ver[1]:
        cell.font = Font(name="Noto Sans CJK SC", bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="245B55")
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    for row in ver.iter_rows(min_row=2):
        for cell in row:
            cell.font = Font(name="Noto Sans CJK SC", size=10)
            cell.alignment = Alignment(wrap_text=True, vertical="top")
        ver.row_dimensions[row[0].row].height = 48
    wb.properties.title = "收购项目法律尽调需求跟踪台账"
    wb.properties.subject = "国城矿业收购国城实业40%股权，本轮公开披露材料缺口"
    wb.save(path)


def build_pdf(path: Path):
    rows = [
        ("CN-1225327554.pdf", "2026年5月交易报告书草案", "历史披露版本"),
        ("CN-1225449388.pdf", "2026年7月修订稿；财务报告期更新至2026-04-30", "本轮披露口径"),
        ("CN-1225327560.pdf", "8-580；2024、2025年度及年末", "不含2026年1-4月"),
        ("CN-1225449390.pdf", "8-650；新增2026-04-30及2026年1-4月", "加期审计版本"),
        ("CN-1225327559.pdf / CN-1225449382.pdf", "5月法律意见书 / 7月补充法律意见（一）", "均为扫描件，逐页核读并索取可检索原件"),
        ("CN-1225449371.pdf", "2026-072修订说明公告", "指示修订主题，不替代底层文件"),
    ]
    focus = [
        "交易方案披露：40%股权交易价为236,800.00万元，评估基准日为2025-12-31；需取得评估报告全本及签署版协议核验调整与付款条件。",
        "矿业权：报告书披露扩界扩能手续仍在办理，拟由500万吨/年扩大至800万吨/年；另披露采矿权抵押及相关贷款清偿线索。需核实审批进度、抵押注销与现行有效证照。",
        "报告期合规与关联交易：修订稿披露行政处罚共7起并更新关联交易事项。需逐案取得决定书/整改凭证、关联合同/定价/决策及结算依据。",
        "程序：报告书将已履行的董事会及相关主体内部决策，与尚需股东会及其他依法适用程序分开表述；需取得决议和授权原件并持续跟踪未完成程序。",
        "底层档案：优先补齐交易协议、公司章程/工商内档、股权与出资档案、许可和资产权属、重大合同、劳动社保及争议材料。",
    ]
    escape = lambda value: html.escape(str(value)).replace("\\n", "<br>")
    table_rows = "".join("<tr>" + "".join(f"<td>{escape(cell)}</td>" for cell in row) + "</tr>" for row in rows)
    bullets = "".join(f"<li>{escape(item)}</li>" for item in focus)
    content = "\n".join([
        '<!doctype html><html><head><meta charset="utf-8"><style>',
        "@page { size: A4; margin: 16mm 15mm; }",
        "body { font-family: 'Noto Sans CJK SC'; font-size: 10pt; line-height: 1.5; color: #243332; }",
        "h1 { text-align:center; color:#245B55; font-size:18pt; margin:0 0 5mm; }",
        "h2 { color:#245B55; font-size:12pt; margin:5mm 0 2mm; }",
        "table { width:100%; border-collapse:collapse; font-size:8.5pt; }",
        "th { background:#245B55; color:white; text-align:left; }",
        "th,td { border:0.5pt solid #B9C7C4; padding:5pt; vertical-align:top; }",
        "tr:nth-child(even) td { background:#F2F6F5; }",
        ".meta { text-align:center; } .note { font-size:8pt; color:#465552; }",
        "</style></head><body>",
        "<h1>收购项目法律尽调资料缺口摘要</h1>",
        "<p class=\"meta\">事项：国城矿业拟收购国城实业40%股权　|　本轮截止：2026年7月31日</p>",
        "<h2>一、范围与使用边界</h2>",
        "<p>本摘要依据本轮收到的七份公开披露 PDF，维护资料需求及缺口，不构成完整尽调意见。公开披露、交易方陈述及中介意见均按其证据角色记录，不视为本团队已独立核实。未见委托范围文件、数据室索引、上轮需求/回复或大量底层原件；资料未提供不等于事项不存在或无风险。</p>",
        "<h2>二、文件版本与财务期间</h2><table><thead><tr><th>文件</th><th>身份/期间</th><th>本轮处理</th></tr></thead><tbody>" + table_rows + "</tbody></table>",
        "<h2>三、本轮重点线索与待核事项</h2><ul>" + bullets + "</ul>",
        "<h2>四、跟进要求</h2>",
        "<p>台账共有24项（R01-R24），状态采用已覆盖/部分覆盖/未提供/不适用，并保留披露与独立核实的区分。优先请求原始数据室索引（含路径、上传时间、版本、回复人）、上轮清单及逐项回复，以建立本轮基线。对未提供事项不得推定不存在风险；补件后记录收到日期、版本、审阅结论和关闭依据。逐项需求及追问见 dd_request_tracker.xlsx。</p>",
        "<p class=\"note\">引用索引：R01-R24 对应工作簿“需求跟踪”表；文件编号均为本轮 /workspace/input-data/ 下的原件文件名。</p>",
        "</body></html>",
    ])
    with tempfile.TemporaryDirectory(prefix="law-l03-pdf-") as td:
        source = Path(td) / "summary.html"
        source.write_text(content, encoding="utf-8")
        result = subprocess.run(["libreoffice", "-env:UserInstallation=file://" + td + "/profile", "--headless", "--convert-to", "pdf", "--outdir", td, str(source)], capture_output=True, text=True, timeout=180)
        generated = Path(td) / "summary.pdf"
        if result.returncode != 0 or not generated.is_file():
            raise RuntimeError(f"LibreOffice PDF export failed: {result.stderr} {result.stdout}")
        path.write_bytes(generated.read_bytes())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-data", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    input_dir, out = Path(args.input_data), Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    extract_text(input_dir)
    # Persist incrementally: workbook first, then its companion summary.
    xlsx = out / "dd_request_tracker.xlsx"
    style_workbook(xlsx)
    build_pdf(out / "dd_gap_summary.pdf")
    check = load_workbook(xlsx, read_only=True, data_only=True)
    if check["需求跟踪"].max_row != len(ROWS) + 1:
        raise RuntimeError("tracker row count mismatch")
    if not (out / "dd_gap_summary.pdf").stat().st_size:
        raise RuntimeError("summary PDF was not created")

if __name__ == "__main__":
    main()
