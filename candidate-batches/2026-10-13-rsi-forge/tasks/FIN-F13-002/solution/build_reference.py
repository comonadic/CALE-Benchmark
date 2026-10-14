#!/usr/bin/env python3
import argparse, re
from pathlib import Path
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from docx import Document
from docx.shared import Pt
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from pypdf import PdfReader

FILES={'policy':'hedge_policy.pdf','announcement':'2025_authorization_announcement.pdf','resolution':'2025_authorization_resolution.pdf','report':'halfyear_report_2026.pdf'}
def pdf_text(p): return '\n'.join(x.extract_text() or '' for x in PdfReader(p).pages)
def num(s): return float(s.replace(',',''))
def find(pattern,text,default=None):
 m=re.search(pattern,text,re.S)
 if not m: raise ValueError('missing source fact: '+pattern)
 return num(m.group(1)) if default is None else m.group(1)
def parse(inp):
 t={k:pdf_text(inp/v) for k,v in FILES.items()}
 report=t['report']
 table=re.search(r'期货公司\s+0\s+([\d,]+\.\d+)\s+(-[\d,]+\.\d+)\s+(-[\d,]+\.\d+)\s+([\d,]+\.\d+)\s+([\d,]+\.\d+)\s+([\d,]+\.\d+)\s+([\d.]+)%.*?商业银行\s+0\s+0\s+(-[\d,]+\.\d+)\s+([\d,]+\.\d+).*?合计\s+0\s+([\d,]+\.\d+)\s+(-[\d,]+\.\d+)\s+(-[\d,]+\.\d+)\s+([\d,]+\.\d+)\s+([\d,]+\.\d+)\s+([\d,]+\.\d+)\s+([\d.]+)%',report,re.S)
 if not table: raise ValueError('derivatives table extraction failed')
 g=[num(x) for x in table.groups()]
 # physical page indices are one-based and sourced from the rendered report text.
 dates=re.search(r'现场会议于\s*2025 年\s*(\d+) 月\s*(\d+) 日',t['resolution'],re.S)
 if not dates: raise ValueError('shareholder approval date not found')
 policy=t['policy']
 return {'futures_open':g[0],'futures_fv':g[1],'futures_oci':g[2],'purchases':g[3],'sales':g[4],'futures_close':g[5],'futures_ratio':g[6]/100,'bank_fv':g[7],'bank_oci':g[8],'total_open':g[9],'total_fv':g[10],'total_oci':g[11],'total_purchases':g[12],'total_sales':g[13],'total_close':g[14],'total_ratio':g[15]/100,'combined_pnl':find(r'实际损益\s*金额合计为\s*([\d.]+)\s*亿元',report)*100_000_000,'approval_date':f'2025-{int(dates.group(1)):02d}-{int(dates.group(2)):02d}','commodity_cap_yuan':find(r'保证金最高占用额不超过人民币\s*([\d.]+)\s*亿元',t['announcement'])*100_000_000,'fx_cap_yuan':find(r'最高占用额不超过人民币\s*([\d.]+)\s*亿元开展外汇',t['announcement'])*100_000_000,'stop_loss_pct':find(r'止损目标不得超过该方案交易金额的\s*([\d.]+)\s*%',policy)/100,'report_pct':find(r'净利润的\s*([\d.]+)\s*%且绝对金',policy)/100}
def style(ws):
 ws.freeze_panes='A2'; ws.auto_filter.ref=ws.dimensions
 for c in ws[1]: c.font=Font(bold=True,color='FFFFFF'); c.fill=PatternFill('solid',fgColor='275D5A'); c.alignment=Alignment(wrap_text=True,vertical='center')
 for col in ws.columns:
  width=min(48,max(12,max(len(str(c.value or '')) for c in col)+2))
  ws.column_dimensions[get_column_letter(col[0].column)].width=width
 for row in ws.iter_rows(min_row=2):
  for c in row: c.alignment=Alignment(vertical='top',wrap_text=True)
def build_xlsx(d,out):
 wb=Workbook(); ws=wb.active; ws.title='披露复核'
 ws.append(['主体/指标','原披露值','原单位','换算值（元）','核查/计算','来源'])
 rows=[('期货公司期初金额',d['futures_open'],'万元', '=B2*10000','期间期初存量','2026半年报 p.24 衍生品投资表'),('期货公司本期公允价值变动损益',d['futures_fv'],'万元','=B3*10000','期间损益流量','同上'),('期货公司计入权益累计公允价值变动',d['futures_oci'],'万元','=B4*10000','累计权益变动，不等同本期损益','同上'),('期货公司报告期购入金额',d['purchases'],'万元','=B5*10000','期间购入流量','同上'),('期货公司报告期售出金额',d['sales'],'万元','=B6*10000','期间售出流量','同上'),('期货公司期末金额',d['futures_close'],'万元','=B7*10000','期末存量；与合计行核对','同上'),('期货公司期末金额占净资产',d['futures_ratio'],'比例','=B8','原披露 2.70%','同上'),('商业银行本期公允价值变动损益',d['bank_fv'],'万元','=B9*10000','期间损益流量','同上'),('商业银行计入权益累计公允价值变动',d['bank_oci'],'万元','=B10*10000','累计权益变动','同上'),('合计期初金额',d['total_open'],'万元','=B11*10000','与期货公司期初勾稽','同上'),('合计本期公允价值变动损益',d['total_fv'],'万元','=B12*10000','应等于期货公司与商业银行之和','同上'),('合计计入权益累计公允价值变动',d['total_oci'],'万元','=B13*10000','应等于期货公司与商业银行之和','同上'),('合计购入金额',d['total_purchases'],'万元','=B14*10000','与期货公司购入金额勾稽','同上'),('合计售出金额',d['total_sales'],'万元','=B15*10000','与期货公司售出金额勾稽','同上'),('合计期末金额',d['total_close'],'万元','=B16*10000','与期货公司期末金额勾稽','同上'),('合计期末金额占净资产',d['total_ratio'],'比例','=B17','原披露 2.70%','同上'),('期现相抵实际损益',d['combined_pnl'],'元','=B18','披露约 2.9 亿元；非逐笔重算','2026半年报 p.24 报告期实际损益说明')]
 for r in rows: ws.append(list(r))
 for r in [8,17]: ws.cell(r,2).number_format='0.00%'; ws.cell(r,4).number_format='0.00%'
 for r in range(2,19):
  if r not in (8,17): ws.cell(r,2).number_format='#,##0.00;[Red]-#,##0.00'; ws.cell(r,4).number_format='#,##0.00;[Red]-#,##0.00'
 ws['A20']='勾稽'; ws['B20']='期货+银行本期公允价值变动'; ws['C20']='=B3+B9'; ws['D20']='合计披露'; ws['E20']='=B12'; ws['F20']='差异（元）'; ws['G20']='=C20*10000-E20'
 ws['A21']='勾稽'; ws['B21']='期货+银行计入权益累计变动'; ws['C21']='=B4+B10'; ws['D21']='合计披露'; ws['E21']='=B13'; ws['F21']='差异（元）'; ws['G21']='=C21*10000-E21'
 ws['A22']='净资产比例复算'; ws['B22']='期末合计金额/披露比例'; ws['C22']='=D16/D17'; ws['D22']='披露值'; ws['E22']='=D17'; ws['F22']='复算百分比'; ws['G22']='=C22'
 ws['G22'].number_format='0.00%'
 auth=wb.create_sheet('授权与条款'); auth.append(['事项','复核值/条款','适用性判断','来源'])
 authrows=[('2025股东会通过日',d['approval_date'],'通过日起12个月滚动使用；覆盖2026H1','2025决议公告 p.2议案5'),('2025商品套保保证金额度（元）',d['commodity_cap_yuan'],'40亿元保证金额度；不含实物交割款','2025-041公告 p.1-2'),('2025外汇套保额度（元）',d['fx_cap_yuan'],'47亿元最高占用额','2025-041公告 p.1-2'),('2026后续授权','2026-08-21股东会通过','发生在2026H1之后，不追溯适用','2026-045公告；2026-049决议'),('方案止损目标',d['stop_loss_pct'],'不得超过该方案交易金额10%；套期工具与被套期项目价值变动可合并适用','管理制度第十三条'),('损失披露条件',f"已确认损益及浮动亏损达到最近一年经审计归母净利润的{d['report_pct']:.0%}且绝对金额超过1000万元",'适用合并计算可包含套期工具与被套期项目变动','管理制度第三十条')]
 for r in authrows: auth.append(list(r))
 gap=wb.create_sheet('证据及缺口'); gap.append(['证据状态/事项','当前可得材料','缺少的证据','影响/后续动作'])
 for r in [('公开披露锚点','2026H1半年报衍生品汇总表与2.9亿元期现相抵损益披露','逐笔采购、销售、库存、定价日、数量和作价记录','不能重建现货敞口或重算期现综合损益；补取期间逐笔现货台账'),('衍生品交易快照','半年报汇总列示期货公司/商业银行金额','完整成交、持仓、结算、保证金账户、交易主体和交易所参数快照','不能计算手数、敞口、保证金占用或验证额度使用；补取经纪商结算单及内部账户日快照'),('方案级风险控制','管理制度描述止损及审批流程','各套保方案、审批单、建仓/平仓、止损触发和例外审批记录','不能判断方案级止损执行或是否存在裸露投机；逐方案补件后复核'),('期现主体对应','2025公告说明交易主体与现货主体未能一一对应','公司内部主体映射、套保指定关系及会计分摊依据','单凭公开汇总无法逐实体配对；补取主体映射和指定文档')]: gap.append(list(r))
 for s in wb.worksheets: style(s)
 out.mkdir(parents=True,exist_ok=True); wb.save(out/'hedge_review.xlsx')

def shade(cell,color):
 tcPr=cell._tc.get_or_add_tcPr(); shd=OxmlElement('w:shd'); shd.set(qn('w:fill'),color); tcPr.append(shd)
def build_pdf(d,out):
 doc=Document(); sec=doc.sections[0]; sec.top_margin=Pt(48); sec.bottom_margin=Pt(48)
 styles=doc.styles; styles['Normal'].font.name='Noto Sans CJK SC'; styles['Normal']._element.rPr.rFonts.set(qn('w:eastAsia'),'Noto Sans CJK SC'); styles['Normal'].font.size=Pt(10)
 title=doc.add_heading('2026年上半年套期保值披露复核',0); title.alignment=WD_ALIGN_PARAGRAPH.CENTER
 p=doc.add_paragraph('复核对象：广东海大集团股份有限公司合并披露 | 期间：2026-01-01 至 2026-06-30'); p.alignment=WD_ALIGN_PARAGRAPH.CENTER
 doc.add_heading('结论摘要',1)
 doc.add_paragraph('半年报列示期货公司期末金额64,041.81万元（640,418,100元），占期末净资产2.70%；本期公允价值变动损益为-4,639.58万元，计入权益的累计公允价值变动为-10,718.22万元。合计行的本期损益-5,247.59万元、权益累计变动-10,381.95万元，分别等于期货公司与商业银行两行之和。报告另披露期现盈亏相抵后的实际损益合计2.9亿元，该数为披露结论，现有材料无逐笔数据支持重算。')
 doc.add_heading('披露勾稽与口径',1)
 table=doc.add_table(rows=1, cols=3); table.alignment=WD_TABLE_ALIGNMENT.CENTER; table.style='Table Grid'
 for c,v in zip(table.rows[0].cells,['项目','披露值','复核意见']): c.text=v; shade(c,'275D5A')
 for c in table.rows[0].cells:
  for r in c.paragraphs[0].runs: r.font.color.rgb=__import__('docx').shared.RGBColor(255,255,255); r.bold=True
 for row in [('期末衍生品金额','64,041.81万元','期末存量，不是期间成交流量'),('期货公司本期公允价值变动','-4,639.58万元','期间损益'),('期货公司计入权益累计变动','-10,718.22万元','累计权益变动，与本期损益口径不同'),('合计本期公允价值变动','-5,247.59万元','-4,639.58 + -608.01 = -5,247.59万元'),('合计计入权益累计变动','-10,381.95万元','-10,718.22 + 336.27 = -10,381.95万元'),('期现相抵实际损益','2.9亿元','半年报披露值；不能由汇总衍生品表单独推算')]:
  cells=table.add_row().cells
  for c,v in zip(cells,row): c.text=v; c.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
 doc.add_paragraph('来源：2026年半年度报告第24页“衍生品投资情况”表及“报告期实际损益情况的说明”。万元换算人民币元按×10,000。期末占比核对：64,041.81万元 / 披露2.70%约对应期末净资产，百分比经四舍五入。')
 doc.add_heading('授权与政策',1)
 doc.add_paragraph(f"2025-043股东会决议载明《关于开展套期保值业务的议案》于2025年8月14日通过；2025-041公告列示商品套保保证金最高40亿元、外汇套保最高占用47亿元，期限自股东会通过日起12个月滚动。故在期间层面，2025授权覆盖2026年上半年。2026年8月21日股东会通过的是后续授权，晚于本复核期间，不用于追溯判断。来源：2025-043公告第2页；2025-041公告第1-2页；2026-049决议公告及2026-045公告。")
 doc.add_paragraph(f"《商品套期保值业务管理制度》第十三条规定方案止损目标不超过该方案交易金额10%，可将套期工具与被套期项目价值变动合并适用；第三十条规定已确认损益及浮动亏损达到最近一年经审计归母净利润10%且绝对金额超过1,000万元时及时披露，也可将套期工具与被套期项目价值变动合并适用。汇总披露不能证明具体方案的止损执行，也不足以独立判定阈值是否触发。")
 doc.add_heading('证据边界与补件',1)
 for x in ['未提供逐笔现货采购、销售、库存、定价日、数量与作价台账，无法复原逐日现货净敞口或独立重算2.9亿元。','衍生品成交、持仓、结算、保证金账户及适用交易所合约参数不完整，无法复算合约手数、保证金占用、交易额度使用或期末持仓。','未提供逐方案审批、套保指定关系、交易指令、日结算单、止损触发及例外审批记录，无法判断方案层面的止损合规与现货/衍生品匹配。','建议补取上述期间逐笔现货台账、完整衍生品交易和账户日快照、内部主体/套保指定映射及方案审批与止损档案后再完成交易级复核。']:
  doc.add_paragraph(x,style='List Bullet')
 doc.add_paragraph('另据2025-041公告第6节，商品交易账户由母公司统一管理，交易主体与各子公司现货主体未能一一对应；逐实体核对需依赖内部主体映射，不能仅以公开汇总表推定。')
 out.mkdir(parents=True,exist_ok=True); doc.save(out/'hedge_review.docx')
 # export with LibreOffice
 import subprocess
 subprocess.run(['libreoffice','-env:UserInstallation=file:///tmp/lo-profile-reference','--headless','--convert-to','pdf','--outdir',str(out),str(out/'hedge_review.docx')],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
if __name__=='__main__':
 ap=argparse.ArgumentParser(); ap.add_argument('--input-data',required=True); ap.add_argument('--output',required=True); a=ap.parse_args(); d=parse(Path(a.input_data)); build_xlsx(d,Path(a.output)); build_pdf(d,Path(a.output))
