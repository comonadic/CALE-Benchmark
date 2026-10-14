#!/usr/bin/env python3
import os, re, shutil
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
import openpyxl
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.worksheet.datavalidation import DataValidation
from pypdf import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table as PdfTable, TableStyle, PageBreak
from reportlab.lib import colors

ROOT=Path('/workspace'); IN=ROOT/'input-data'; OUT=ROOT/'output'; OUT.mkdir(exist_ok=True)

def pdf_text(name):
    r=PdfReader(str(IN/name)); return '\n'.join(p.extract_text() or '' for p in r.pages)
trustee=pdf_text('02_申万宏源2025年度受托报告.pdf')
payment=pdf_text('03_23申宏04兑付公告.pdf')
annual=pdf_text('01_申万宏源2025年度报告.pdf')
notice=(IN/'04_新疆证监局2026通知.html').read_text(encoding='utf-8',errors='replace')
# Extract the disclosed debt row and payment terms from source text.
row_re=re.compile(r'债券简称\s+21 申宏 06.*?起息日\s+2021 年 8 月 4 日.*?到期日\s+2026 年 8 月 4 日.*?发行规模（亿元）\s+25\.00.*?债券余额（亿元）\s+25\.00.*?债券利率（%）\s+3\.38',re.S)
if not row_re.search(trustee): raise RuntimeError('21申宏06 source row not found')
# The source table states annual interest, single interest, and no enhancement.
principal=25.00; rate=0.0338; interest=round(principal*rate,2); total=round(principal+interest,2)
cutoff='2026-07-31'; due='2026-08-04'; pay='2026-08-04'
code='149579.SZ'; short='21申宏06'
# Build from the official template and retain its visible fields/notes.
tmpl=IN/'05_附件5排查表模板.xlsx'; wb=load_workbook(tmpl)
ws=wb['Sheet1']; ws.title='排查表'
# Remove the template's very wide decorative merged range footprint after preserving notes.
for rng in list(ws.merged_cells.ranges):
    if rng.min_row<=3 and rng.max_col>17: ws.unmerge_cells(str(rng))
# clear data rows only, not notes
for r in range(4,9):
    for c in range(1,18): ws.cell(r,c).value=None
headers=['序号','证券代码','证券简称','发行人中文名称','债券类别','公司属性','证监会行业名称','债券余额（亿元）','受托管理人','行权日期','日期性质','风险分类','风险情况','兑付资金落实情况','兑付资金来源','上市公司代码（如有）','备注']
for c,h in enumerate(headers,1):
    ws.cell(3,c).value=h
values=[1,code,short,'申万宏源集团股份有限公司','公司债券','中央国有企业','金融业',principal,'财信证券股份有限公司',due,'到期','正常类','截至排查日未见受托报告所述违约、重大事项或评级下调；但本次专项资金证明未提供，需补证。','未落实','发行人自有资金兑付（待提供专用资金证明）','000166','合同到期日：2026-08-04；实际付款节点按受托报告披露的年付息/到期安排登记为2026-08-04。专项资金到账及可用性待核实。']
for c,v in enumerate(values,1): ws.cell(4,c).value=v
# Add a calculation/evidence sheet with formulas, provenance, and status.
calc=wb.create_sheet('计算与证据')
calc_headers=['证券简称','本金（亿元）','票面利率','当期利息（亿元）','本金及利息合计（亿元）','排查日','合同到期/回售日','实际付款节点','余额依据','日期/条款依据','资金证明状态','资金可用性','预计到账时点','去重核对','更新时间']
for c,h in enumerate(calc_headers,1): calc.cell(1,c).value=h
row=[short,principal,rate,None,None,cutoff,due,pay,'受托报告PDF第8页（原件页码7）：余额25.00亿元','受托报告PDF第8页；附件5通知说明次月到期排查','未提供专项资金证明','待发行人补充银行流水/资金归集证明','未明确；须在T-2前核实划付安排','本排查仅一只债券，暂无跨券重复覆盖；仍须取得来源证明',cutoff]
for c,v in enumerate(row,1): calc.cell(2,c).value=v
calc['D2']='=ROUND(B2*C2,2)'; calc['E2']='=ROUND(B2+D2,2)'
calc['A4']='汇总'; calc['B4']='=SUM(B2:B2)'; calc['D4']='=SUM(D2:D2)'; calc['E4']='=SUM(E2:E2)'
calc['A6']='证据索引'; calc['A7']='受托报告'; calc['B7']='02_申万宏源2025年度受托报告.pdf，第8页（原件PDF页码，债券基本情况）'; calc['A8']='新疆通知'; calc['B8']='04_新疆证监局2026通知.html，二（三）每月初摸排次月到期情况，10日前报送附件5；二（四）兑付日前1周资金未落实或重大不确定性时报告'; calc['A9']='附件5'; calc['B9']='05_附件5排查表模板.xlsx，字段与注1-5'; calc['A10']='年度报告'; calc['B10']='01_申万宏源2025年度报告.pdf，第419页（原件页码418）：2025-12-31合并金融负债到期结构；第20页（原件页码19）：期末现金及现金等价物1,883.91亿元'; calc['A11']='兑付公告'; calc['B11']='03_23申宏04兑付公告.pdf，第1-3页：另一只债券的实际兑付节点/登记日示例，不作为本次债券来源'
for col in range(1,16): calc.cell(1,col).font=Font(bold=True,color='FFFFFF'); calc.cell(1,col).fill=PatternFill('solid',fgColor='1F4E78'); calc.cell(1,col).alignment=Alignment(wrap_text=True,vertical='center')
for sheet in [ws,calc]:
    sheet.freeze_panes='A4' if sheet==ws else 'A2'
    for rowcells in sheet.iter_rows():
        for cell in rowcells: cell.alignment=Alignment(wrap_text=True,vertical='top')
    for col in range(1,min(sheet.max_column,20)+1): sheet.column_dimensions[openpyxl.utils.get_column_letter(col)].width=16
for c in ['D','Q']: ws.column_dimensions[c].width=25
ws.column_dimensions['M'].width=34; ws.column_dimensions['N'].width=22; ws.column_dimensions['O'].width=28
for c in ['B','J','K','L','M','N','O']: calc.column_dimensions[c].width=25
calc.column_dimensions['B'].width=46
for r in [4]: ws.row_dimensions[r].height=75
ws.auto_filter.ref='A3:Q4'
# validation lists
for col,vals2 in [('K','到期,回售'),('L','正常类,关注类,风险类,违约类'),('N','已落实,未落实,落实中')]:
    dv=DataValidation(type='list',formula1='"'+vals2+'"'); ws.add_data_validation(dv); dv.add(ws[f'{col}4'])
# Add a proper table around the filled row.
tab=Table(displayName='FundingCheck',ref='A3:Q4'); tab.tableStyleInfo=TableStyleInfo(name='TableStyleMedium2',showRowStripes=True,showColumnStripes=False); ws.add_table(tab)
wb.calculation.fullCalcOnLoad=True; wb.calculation.forceFullCalc=True; wb.calculation.calcMode='auto'
wb.save(OUT/'debt_funding_check.xlsx')

# PDF memo generated from source-derived values.
pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
base='STSong-Light'
styles=getSampleStyleSheet(); styles.add(ParagraphStyle(name='CN',fontName=base,fontSize=9.5,leading=15)); styles.add(ParagraphStyle(name='TitleCN',fontName=base,fontSize=16,leading=22,alignment=TA_CENTER)); styles.add(ParagraphStyle(name='HeadCN',fontName=base,fontSize=11,leading=17,spaceBefore=8,spaceAfter=4))
doc=SimpleDocTemplate(str(OUT/'funding_risk_note.pdf'),pagesize=A4,rightMargin=18*mm,leftMargin=18*mm,topMargin=16*mm,bottomMargin=16*mm)
story=[Paragraph('申万宏源集团公司债券到期资金落实重点风险说明',styles['TitleCN']),Paragraph('排查截止日：2026年7月31日　辖区：新疆　报送周期：2026年8月',styles['CN']),Spacer(1,6)]
story += [Paragraph('一、排查范围与规则',styles['HeadCN']),Paragraph('依据《新疆证监局关于做好2026年新疆辖区债券相关工作的通知》二（三），受托管理人应在每月初摸排辖区次月受托债券到期情况和偿债资金落实情况，并于每月10日前报送附件5。二（四）要求兑付日前1周资金仍未落实或经研判存在重大不确定性的，第一时间电话报告并在2个工作日内报送重大事项报告单。本次以2026年7月31日为截止日，范围限定为2026年8月到期或回售且截至截止日仍存续的财信证券受托债券。',styles['CN'])]
story += [Paragraph('二、逐券金额与节点',styles['HeadCN'])]
data=[['证券代码','简称','余额/本金（亿元）','利率','利息（亿元）','合计（亿元）','合同到期日','实际付款节点'],[code,short,f'{principal:.2f}','3.38%',f'{interest:.2f}',f'{total:.2f}',due,pay]]
t=PdfTable(data,colWidths=[22*mm,22*mm,28*mm,16*mm,24*mm,25*mm,25*mm,25*mm]); t.setStyle(TableStyle([('FONTNAME',(0,0),(-1,-1),base),('FONTSIZE',(0,0),(-1,-1),7.5),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#1F4E78')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('GRID',(0,0),(-1,-1),.3,colors.grey),('VALIGN',(0,0),(-1,-1),'TOP'),('ALIGN',(0,0),(-1,-1),'CENTER')]))
story += [t,Paragraph('本金25.00亿元、年利息=25.00×3.38%=0.845亿元，按金额单位保留两位为0.85亿元；本金及利息合计25.85亿元。余额和条款依据：02_申万宏源2025年度受托报告.pdf第8页（原件页码7）。实际付款节点按该债券年付息、到期一次性还本安排登记为2026年8月4日；如登记机构或交易规则后续公告顺延，应更新本表。',styles['CN'])]
story += [Paragraph('三、资金来源、落实状态与去重',styles['HeadCN']),Paragraph('截至排查日，输入材料没有提供针对21申宏06的银行流水、偿债专户余额、资金归集回单、融资提款通知或其他可核验的专项资金证明。因此，"发行人自有资金兑付"只能作为待补证的计划性来源，不能作为已落实资金计入覆盖金额。已取得、可用且有到账时点证据的资金：0.00亿元；待确认/落实中的计划性来源：25.85亿元（不计入已落实覆盖）；可核实缺口：25.85亿元。因本期排查范围只有一只债券，表内无跨券重复覆盖；取得证明后仍需将资金来源ID、可用余额、到账日期与本债券一一对应。',styles['CN'])]
story += [Paragraph('四、财务、重大事项与增信观察',styles['HeadCN']),Paragraph('受托报告第20页（原件页码19）披露2025年末合并期末现金及现金等价物1,883.91亿元；第419页（原件页码418）披露合并金融负债按合同期限的结构，其中应付债券账面价值合计1,231.60亿元。上述是合并口径、期末时点的财务背景，不等于本次25.85亿元已划入指定兑付账户。受托报告第16-17页披露受托人持续监测并核实偿债资金筹措、归集情况；第24页（原件页码23）披露各期债券为无担保发行、增信措施未发生变化；第28页（原件页码27）披露主体及相关债项维持AAA、展望稳定。无担保和缺少专项证明意味着仍需取得可用性和时点证据，评级与期末现金不能替代到账证明。',styles['CN'])]
story += [Paragraph('五、跟进与报告清单',styles['HeadCN']),Paragraph('优先级1（立即）：向发行人索取21申宏06偿债专户/指定账户资金余额、银行流水或回单、资金归集通知和可用性承诺，并核对金额至少覆盖25.85亿元及到账节点；在兑付日前一周仍未取得证明或研判存在重大不确定性时，按通知二（四）第一时间电话报告新疆证监局，并在2个工作日内报送重大事项报告单。优先级2（兑付前）：逐日更新资金到位状态；核对公司债券规则要求的提前划款节点，保留登记机构确认。优先级3（报送）：在每月10日前按附件5报送加盖公章扫描版及Excel版，更新填表人和联系信息；如资金从拟发行债券或银行借款取得，补录预计发行/到账时间，防止重复覆盖。',styles['CN'])]
doc.build(story)
print('generated',OUT/'debt_funding_check.xlsx',OUT/'funding_risk_note.pdf')
