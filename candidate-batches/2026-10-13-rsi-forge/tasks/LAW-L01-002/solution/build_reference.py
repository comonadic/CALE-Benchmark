#!/usr/bin/env python3
import argparse, copy, re, zipfile
from pathlib import Path
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.text.run import Run

AUTHOR = "法律顾问"
DATE = "2026-10-13T00:00:00Z"


def clear_paragraph(p):
    for child in list(p._p):
        if child.tag != qn("w:pPr"):
            p._p.remove(child)


def plain_run(p, text):
    r = p.add_run(text)
    return r


def marked_run(p, text, kind, ident):
    r = OxmlElement("w:r")
    t = OxmlElement("w:t") if kind == "ins" else OxmlElement("w:delText")
    if text[:1].isspace() or text[-1:].isspace():
        t.set(qn("xml:space"), "preserve")
    t.text = text
    r.append(t)
    wrapper = OxmlElement("w:" + kind)
    wrapper.set(qn("w:id"), str(ident))
    wrapper.set(qn("w:author"), AUTHOR)
    wrapper.set(qn("w:date"), DATE)
    wrapper.append(r)
    p._p.append(wrapper)
    return Run(r, p)


def replace_with_redline(p, old, new, ident, comment):
    text = p.text
    if old not in text:
        return False
    before, after = text.split(old, 1)
    clear_paragraph(p)
    if before:
        plain_run(p, before)
    marked_run(p, old, "del", ident)
    inserted = marked_run(p, new, "ins", ident + 1)
    if after:
        plain_run(p, after)
    return inserted, comment


def make_clean_doc(source, output):
    d = Document(source)
    for p in d.paragraphs:
        text = p.text
        text = text.replace("CZ2026-xxxx", "CZ2026-0463")
        text = text.replace("巡检、s维修、保养", "巡检、维修、保养")
        if "（一）合同签订后" in text or "（二）服务满6个月" in text or "（三）服务满9个月" in text or "（四）服务期自" in text:
            text = text.replace("收到发票后10个工作日内办理财政集中支付手续", "收到发票后5个工作日内办理财政集中支付手续")
            text = text.replace("自收到发票之日起10个工作日内办理财政集中支付手续", "自收到发票之日起5个工作日内办理财政集中支付手续")
        if text == "考核与验收":
            text = "七、考核与验收"
        if "不得转包或分包项目内容" in text:
            text = text.replace("乙方不得转包或分包项目内容，但运维范围内的产品或服务按相关规定或约定由其经营者或专业机构负责维修维护的、提供的，从其规定或约定；", "乙方不得违法转包；合同分包应符合招标文件和采购需求关于分包、中小企业份额及资质条件的规定；")
        if "合同期届满后，甲方和监理单位组织对乙方进行合同验收" in text:
            text = "服务期满9个月时，乙方提交初步验收申请，甲方在收到申请后7日内组织履约初步验收；合同期届满后按附件2进行合同验收，甲方在收到申请后10个工作日内组织验收。"
        if "合同服务费总价为不超过" in text:
            text = text + "合同金额及分期比例应以中标结果和采购需求付款方式最终核对确认。"
        if "六、合同总价及付款方式" in text:
            text = text + "采购需求关于付款期限、分期比例及绩效考核款的明确约定优先适用；本合同与其不一致的，应在签署前统一。"
        if text != p.text:
            clear_paragraph(p)
            plain_run(p, text)
    # Add a short cross-reference in a stable location if the source has no such text.
    d.save(output)


def make_redline(source, output):
    d = Document(source)
    comments = []
    ident = 100
    for p in d.paragraphs:
        text = p.text
        replacements = []
        if "CZ2026-xxxx" in text:
            replacements.append(("CZ2026-xxxx", "CZ2026-0463", "项目编号应与招标文件统一为CZ2026-0463。"))
        if "巡检、s维修、保养" in text:
            replacements.append(("巡检、s维修、保养", "巡检、维修、保养", "更正原文拼写错误，避免履约范围产生歧义。"))
        if "（一）合同签订后" in text or "（二）服务满6个月" in text or "（三）服务满9个月" in text or "（四）服务期自" in text:
            if "收到发票后10个工作日内办理财政集中支付手续" in text:
                replacements.append(("收到发票后10个工作日内办理财政集中支付手续", "收到发票后5个工作日内办理财政集中支付手续", "采购需求P272-P275明确为收到发票后5个工作日，且P270规定其付款方式不一致时优先适用。"))
            if "自收到发票之日起10个工作日内办理财政集中支付手续" in text:
                replacements.append(("自收到发票之日起10个工作日内办理财政集中支付手续", "自收到发票之日起5个工作日内办理财政集中支付手续", "采购需求付款期限为5个工作日，应统一合同表述。"))
        if "乙方不得转包或分包项目内容" in text:
            old = "乙方不得转包或分包项目内容，但运维范围内的产品或服务按相关规定或约定由其经营者或专业机构负责维修维护的、提供的，从其规定或约定；"
            new = "乙方不得违法转包；合同分包应符合招标文件和采购需求关于分包、中小企业份额及资质条件的规定；"
            replacements.append((old, new, "招标文件允许合同分包，采购需求要求中小企业份额40%且小微企业不低于28%；原句与采购文件冲突。"))
        if text == "考核与验收":
            replacements.append(("考核与验收", "七、考核与验收", "补足缺失的第七章编号，便于条款引用和交叉核对。"))
        if "验收：合同期届满后按附件2进行" in text:
            old = text
            new = "验收：服务期满9个月时，乙方提交初步验收申请，甲方在收到申请后7日内组织履约初步验收；合同期届满后按附件2进行合同验收，甲方在收到申请后10个工作日内组织验收。"
            replacements.append((old, new, "采购需求P276-P282设置9个月初步验收（7日内）和12个月合同验收，原合同遗漏前者。"))
        if "六、合同总价及付款方式" in text:
            old = text
            new = text + "采购需求关于付款期限、分期比例及绩效考核款的明确约定优先适用；本合同与其不一致的，应在签署前统一。"
            replacements.append((old, new, "将采购需求P270的优先适用规则显式纳入合同，避免付款冲突。"))
        if replacements:
            # Apply one replacement per paragraph by rebuilding the paragraph once.
            current = text
            chunks = []
            cursor = 0
            usable = []
            for old, new, note in replacements:
                pos = current.find(old, cursor)
                if pos >= 0:
                    usable.append((pos, old, new, note))
                    cursor = pos + len(old)
            if usable:
                clear_paragraph(p)
                cursor = 0
                anchor = None
                for pos, old, new, note in usable:
                    if pos > cursor:
                        plain_run(p, current[cursor:pos])
                    marked_run(p, old, "del", ident)
                    anchor = marked_run(p, new, "ins", ident + 1)
                    comments.append((anchor, note))
                    ident += 2
                    cursor = pos + len(old)
                if cursor < len(current):
                    plain_run(p, current[cursor:])
    # Add comments after all XML edits so the comment anchors point to real runs.
    for anchor, text in comments:
        d.add_comment(anchor, text=text, author=AUTHOR, initials="LF")
    d.save(output)


def make_opinion(output):
    d = Document()
    d.add_heading("合同审查意见", level=1)
    d.add_paragraph("审查立场：本意见代表广州市人民政府办公厅，基于合同原件、采购需求和招标文件原始归档进行签署前复核。意见只处理材料能够证明的事项，不替业务部门补造中标价、乙方主体或谈判确认记录。")
    d.add_heading("一、已在修订稿处理的事项", level=2)
    items = [
        "项目编号由CZ2026-xxxx统一为CZ2026-0463。",
        "付款条款由收到发票后10个工作日统一为5个工作日，并明确采购需求付款方式的优先适用；分期比例仍须结合中标结果核对。",
        "删除与采购文件冲突的绝对禁止分包表述，改为遵守招标文件、采购需求的分包、中小企业份额和资质条件。",
        "补入9个月初步验收及7日组织期限，保留12个月合同验收及10个工作日期限。",
        "补足“七、考核与验收”章节编号，并更正“s维修”拼写。",
    ]
    for item in items:
        d.add_paragraph(item, style="List Bullet")
    d.add_heading("二、签署前待确认", level=2)
    for item in [
        "中标总价、合同总额及大写金额；不得以预算金额直接替代中标价。",
        "乙方名称、地址、法定代表人、授权签约代表、开户银行、账号和行号。",
        "约30%/30%/20%/20%的四期进度款与约20%绩效考核款如何在合同金额中计算，及其与绩效等级的对应关系。",
        "采购需求要求合同分包中中小企业达到40%，其中预留给小微企业不低于28%；该比例属于采购条件，签署前核对分包方案。",
        "附件1绩效考核方案、附件2验收标准、附件3保密协议的最终版本和签署主体；项目团队保密协议应落实。",
        "初步验收申请材料、监理单位参与方式，以及不合格整改10日的起算点。",
        "履约保证金是否适用及其金额、提交期限和退还条件；现有合同正文未载明。",
    ]:
        d.add_paragraph(item, style="List Bullet")
    d.add_heading("三、立场与谈判建议", level=2)
    d.add_paragraph("采购文件明确的付款、验收和分包条件属于应保持一致的履约法律底线；合同中的主体和金额空白属于签署前事实核验事项。甲方逾期付款3‰/日且累计不超过合同总额5%、乙方违约金10%的不对称安排属于采购人现有风险分配，不因本轮校核而当然改成单向加重；是否调整应由业务部门结合采购文件和谈判记录作商业决定。")
    d.add_heading("四、材料依据", level=2)
    d.add_paragraph("合同原件第五章；采购需求P210、P258、P266、P270-P282；招标文件采购项目编号、预算金额、合同履行期限及合同分包要求。")
    d.save(output)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-data", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    inp = Path(args.input_data); out = Path(args.output); out.mkdir(parents=True, exist_ok=True)
    source = inp / "contract_original.docx"
    make_redline(source, out / "contract_redline.docx")
    make_clean_doc(source, out / "contract_clean.docx")
    make_opinion(out / "review_opinion.docx")
    (out / "worklog.md").write_text("# 增量工作记录\n\n- 已读取三份原始出版物并建立问题矩阵。\n- 已生成修订稿、清洁稿和审查意见。\n- 金额、乙方主体和银行信息保留待确认。\n", encoding="utf-8")

if __name__ == "__main__":
    main()
