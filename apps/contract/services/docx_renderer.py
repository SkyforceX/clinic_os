
from __future__ import annotations

from copy import deepcopy
from datetime import date
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION_START
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_ROW_HEIGHT_RULE, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn, nsdecls
from docx.shared import Cm, Pt, RGBColor


QUOTATION_TABLE_MARKER = "{{ QUOTATION_TABLE }}"


def _iter_all_tables(parent):
    for table in getattr(parent, "tables", []):
        yield table
        for row in table.rows:
            for cell in row.cells:
                yield from _iter_all_tables(cell)


def _iter_all_paragraphs(parent):
    for paragraph in getattr(parent, "paragraphs", []):
        yield paragraph
    for table in getattr(parent, "tables", []):
        for row in table.rows:
            for cell in row.cells:
                yield from _iter_all_paragraphs(cell)


def _replace_text_in_paragraph(paragraph, replacements: dict):
    full_text = "".join(run.text for run in paragraph.runs) if paragraph.runs else paragraph.text
    if not full_text:
        return

    replaced = full_text
    for key, value in replacements.items():
        replaced = replaced.replace(key, str(value or ""))

    if replaced == full_text:
        return

    if paragraph.runs:
        paragraph.runs[0].text = replaced
        for run in paragraph.runs[1:]:
            run.text = ""
    else:
        paragraph.text = replaced


def _replace_text_everywhere(doc: Document, replacements: dict):
    for paragraph in _iter_all_paragraphs(doc):
        _replace_text_in_paragraph(paragraph, replacements)

    for section in doc.sections:
        for paragraph in _iter_all_paragraphs(section.header):
            _replace_text_in_paragraph(paragraph, replacements)
        for paragraph in _iter_all_paragraphs(section.footer):
            _replace_text_in_paragraph(paragraph, replacements)


def _remove_paragraph(paragraph):
    p = paragraph._element
    parent = p.getparent()
    if parent is not None:
        parent.remove(p)
    paragraph._p = paragraph._element = None


def _set_cell_shading(cell, fill: str):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)
    shd.set(qn("w:val"), "clear")


def _set_cell_border(cell, **kwargs):
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_borders = tc_pr.first_child_found_in("w:tcBorders")
    if tc_borders is None:
        tc_borders = OxmlElement("w:tcBorders")
        tc_pr.append(tc_borders)

    for edge in ("left", "top", "right", "bottom", "insideH", "insideV"):
        edge_data = kwargs.get(edge)
        if not edge_data:
            continue
        tag = f"w:{edge}"
        element = tc_borders.find(qn(tag))
        if element is None:
            element = OxmlElement(tag)
            tc_borders.append(element)
        for key, value in edge_data.items():
            element.set(qn(f"w:{key}"), str(value))


def _set_cell_margins(cell, top=80, start=90, bottom=80, end=90):
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for side, value in {"top": top, "start": start, "bottom": bottom, "end": end}.items():
        element = tc_mar.find(qn(f"w:{side}"))
        if element is None:
            element = OxmlElement(f"w:{side}")
            tc_mar.append(element)
        element.set(qn("w:w"), str(value))
        element.set(qn("w:type"), "dxa")


def _clear_cell(cell):
    cell._tc.clear_content()
    cell.add_paragraph("")


def _style_runs(paragraph, *, bold=False, italic=False, size=10.5, color=None, font_name="Arial"):
    for run in paragraph.runs:
        run.bold = bold
        run.italic = italic
        run.font.size = Pt(size)
        run.font.name = font_name
        rpr = run._element.get_or_add_rPr()
        rfonts = rpr.rFonts
        if rfonts is None:
            rfonts = OxmlElement("w:rFonts")
            rpr.append(rfonts)
        for attr in ("ascii", "hAnsi", "eastAsia", "cs"):
            rfonts.set(qn(f"w:{attr}"), font_name)
        if color:
            run.font.color.rgb = RGBColor.from_string(color)


def _set_paragraph_spacing(paragraph, before=0, after=0, line=1.0):
    pf = paragraph.paragraph_format
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    pf.line_spacing = line


def _write_cell_text(
    cell,
    text,
    *,
    align=WD_ALIGN_PARAGRAPH.LEFT,
    bold=False,
    italic=False,
    size=10.0,
    color=None,
    shading=None,
):
    _clear_cell(cell)
    p = cell.paragraphs[0]
    p.alignment = align
    p.add_run(str(text or ""))
    _style_runs(p, bold=bold, italic=italic, size=size, color=color)
    _set_paragraph_spacing(p, before=0, after=0, line=1.12)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    _set_cell_margins(cell, top=60, start=70, bottom=60, end=70)
    _set_cell_border(
        cell,
        top={"val": "single", "sz": 8, "color": "1F1F1F"},
        bottom={"val": "single", "sz": 8, "color": "1F1F1F"},
        left={"val": "single", "sz": 8, "color": "1F1F1F"},
        right={"val": "single", "sz": 8, "color": "1F1F1F"},
    )
    if shading:
        _set_cell_shading(cell, shading)


def _set_row_repeat_as_header(row):
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = tr_pr.find(qn("w:tblHeader"))
    if tbl_header is None:
        tbl_header = OxmlElement("w:tblHeader")
        tr_pr.append(tbl_header)
    tbl_header.set(qn("w:val"), "true")


def _set_table_width(table, pct: int = 100):
    tbl_pr = table._tbl.tblPr
    tbl_w = tbl_pr.find(qn("w:tblW"))
    if tbl_w is None:
        tbl_w = OxmlElement("w:tblW")
        tbl_pr.append(tbl_w)
    tbl_w.set(qn("w:type"), "pct")
    tbl_w.set(qn("w:w"), str(pct * 50))


def _set_table_fixed_layout(table):
    tbl_pr = table._tbl.tblPr
    tbl_layout = tbl_pr.find(qn("w:tblLayout"))
    if tbl_layout is None:
        tbl_layout = OxmlElement("w:tblLayout")
        tbl_pr.append(tbl_layout)
    tbl_layout.set(qn("w:type"), "fixed")


def _set_cell_width(cell, width_cm: float):
    width_twips = int(width_cm * 567)
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_w = tc_pr.find(qn("w:tcW"))
    if tc_w is None:
        tc_w = OxmlElement("w:tcW")
        tc_pr.append(tc_w)
    tc_w.set(qn("w:w"), str(width_twips))
    tc_w.set(qn("w:type"), "dxa")
    cell.width = Cm(width_cm)


def _set_table_grid(table, widths_cm: list[float]):
    tbl = table._tbl
    tbl_grid = tbl.tblGrid
    if tbl_grid is not None:
        tbl.remove(tbl_grid)

    tbl_grid = OxmlElement("w:tblGrid")
    for width_cm in widths_cm:
        grid_col = OxmlElement("w:gridCol")
        grid_col.set(qn("w:w"), str(int(width_cm * 567)))
        tbl_grid.append(grid_col)
    tbl.insert(1, tbl_grid)


def _set_table_borders(table, size=4, color="888888"):
    tbl = table._tbl
    tbl_pr = tbl.tblPr

    tbl_borders = tbl_pr.find(qn("w:tblBorders"))
    if tbl_borders is None:
        tbl_borders = OxmlElement("w:tblBorders")
        tbl_pr.append(tbl_borders)

    for border_name in ("top", "left", "bottom", "right", "insideH", "insideV"):
        tag = f"w:{border_name}"
        element = tbl_borders.find(qn(tag))
        if element is None:
            element = OxmlElement(tag)
            tbl_borders.append(element)

        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), str(size))   # 4 = mỏng đẹp
        element.set(qn("w:space"), "0")
        element.set(qn("w:color"), color)


def _move_table_after_paragraph(paragraph, table):
    paragraph._p.addnext(table._tbl)


def _find_table_marker(doc: Document):
    for paragraph in doc.paragraphs:
        if QUOTATION_TABLE_MARKER in paragraph.text:
            return ("document", paragraph)

    for table in _iter_all_tables(doc):
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    if QUOTATION_TABLE_MARKER in paragraph.text:
                        return ("cell", cell, paragraph)

    for section in doc.sections:
        for header_footer in (section.header, section.footer):
            for paragraph in _iter_all_paragraphs(header_footer):
                if QUOTATION_TABLE_MARKER in paragraph.text:
                    return ("header_footer", paragraph)

    return None


def _build_replacements(payload: dict) -> dict:
    quotation = payload["quotation"]
    totals = payload["totals"]
    today = date.today()

    return {
        "{{ issue_day }}": str(today.day),
        "{{ issue_month }}": str(today.month),
        "{{ issue_year }}": str(today.year),
        "{{ issue_date }}": today.strftime("%d/%m/%Y"),
        "{{ quotation_id }}": quotation["id"],
        "{{ quotation_number }}": quotation["id"],
        "{{ company_name }}": quotation["company_name"],
        "{{ contact_name }}": quotation["contact_name"],
        "{{ company_address }}": quotation["company_address"],
        "{{ valid_until }}": quotation["valid_until_display"],
        "{{ pax_from }}": quotation["pax_from"],
        "{{ male_count }}": quotation["male_count"],
        "{{ female_single_count }}": quotation["female_single_count"],
        "{{ female_family_count }}": quotation["female_family_count"],
        "{{ note }}": quotation["note"],
        "{{ total_male }}": totals["total_male_display"],
        "{{ total_female_single }}": totals["total_female_single_display"],
        "{{ total_female_family }}": totals["total_female_family_display"],
        "{{ grand_total }}": totals["grand_total_display"],
    }


def _add_group_row(table, label: str):
    tr = table.add_row()
    tr.height_rule = WD_ROW_HEIGHT_RULE.AT_LEAST
    merged = tr.cells[0].merge(tr.cells[5])
    _write_cell_text(
        merged,
        label,
        bold=True,
        size=10.5,
        color="FFFFFF",
        shading="2F5AA8",
    )
    return tr


def _add_item_row(table, line: dict):
    tr = table.add_row()
    tr.height_rule = WD_ROW_HEIGHT_RULE.AT_LEAST

    service_text = line["item_name"]
    if line["description"]:
        service_text = f"{service_text}\n{line['description']}"

    _write_cell_text(tr.cells[0], line["stt"], align=WD_ALIGN_PARAGRAPH.CENTER, size=10)
    _write_cell_text(tr.cells[1], service_text, align=WD_ALIGN_PARAGRAPH.LEFT, size=10)
    _write_cell_text(
        tr.cells[2],
        line["display_unit_price"] or "",
        align=WD_ALIGN_PARAGRAPH.CENTER,
        bold=bool(line["display_unit_price"]),
        size=10,
        shading="D9E5F6" if line["price_type"] == "standard" else "F6C39A",
    )
    _write_cell_text(tr.cells[3], line["male_mark"], align=WD_ALIGN_PARAGRAPH.CENTER, size=10)
    _write_cell_text(tr.cells[4], line["female_single_mark"], align=WD_ALIGN_PARAGRAPH.CENTER, size=10)
    _write_cell_text(tr.cells[5], line["female_family_mark"], align=WD_ALIGN_PARAGRAPH.CENTER, size=10)
    return tr


def _append_quotation_table(container, payload: dict):
    table = container.add_table(rows=1, cols=6)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    _set_table_borders(table, size=4, color="999999")
    _set_table_width(table, 100)
    _set_table_fixed_layout(table)

    # note must: fit trong khổ A4 portrait sau khi trừ margin.
    widths_cm = [0.95, 7.25, 1.85, 2.55, 2.85, 2.85]
    _set_table_grid(table, widths_cm)

    def _apply_widths(row):
        for idx, width_cm in enumerate(widths_cm):
            _set_cell_width(row.cells[idx], width_cm)

    for row in table.rows:
        _apply_widths(row)

    header = table.rows[0]
    _apply_widths(header)
    _set_row_repeat_as_header(header)
    header.height_rule = WD_ROW_HEIGHT_RULE.AT_LEAST

    headers = [
        "STT",
        "KHÁM TỔNG QUÁT /\nGENERAL EXAMINATION",
        "GIÁ ƯU ĐÃI\n(VND)",
        "NAM",
        "NỮ\nĐỘC THÂN",
        "NỮ\nGIA ĐÌNH",
    ]
    for idx, label in enumerate(headers):
        _write_cell_text(
            header.cells[idx],
            label,
            align=WD_ALIGN_PARAGRAPH.CENTER,
            bold=True,
            size=9.5,
            color="FFFFFF",
            shading="2F5AA8",
        )

    for row in payload["display_rows"]:
        if row["row_type"] == "group":
            tr = _add_group_row(table, row["label"])
            _apply_widths(tr)
            continue
        if row["row_type"] == "subgroup":
            tr = _add_group_row(table, row["label"])
            _apply_widths(tr)
            continue
        tr = _add_item_row(table, row["line"])
        _apply_widths(tr)

    totals = payload["totals"]
    
    tr = table.add_row()
    _apply_widths(tr)
    
    tr.height = Cm(1.2)
    tr.height_rule = WD_ROW_HEIGHT_RULE.EXACTLY
    
    merged = tr.cells[0].merge(tr.cells[2])
    
    _set_cell_width(merged, widths_cm[0] + widths_cm[1] + widths_cm[2])
    
    _write_cell_text(
        merged,
        "Giá trị gói khám theo giá niêm yết tại Phòng khám (VND/người)",
        align=WD_ALIGN_PARAGRAPH.CENTER,
        bold=True,
        size=10,
        color="FFFFFF",
        shading="C96200",
    )
    _write_cell_text(
        tr.cells[3],
        totals["total_male_display"] or "0",
        align=WD_ALIGN_PARAGRAPH.CENTER,
        bold=True,
        size=10,
        color="FFFFFF",
        shading="C96200",
    )
    _write_cell_text(
        tr.cells[4],
        totals["total_female_single_display"] or "0",
        align=WD_ALIGN_PARAGRAPH.CENTER,
        bold=True,
        size=10,
        color="FFFFFF",
        shading="C96200",
    )
    _write_cell_text(
        tr.cells[5],
        totals["total_female_family_display"] or "0",
        align=WD_ALIGN_PARAGRAPH.CENTER,
        bold=True,
        size=10,
        color="FFFFFF",
        shading="C96200",
    )

    tr = table.add_row()
    _apply_widths(tr)
    merged = tr.cells[0].merge(tr.cells[2])
    _write_cell_text(
        merged,
        "TỔNG GIÁ TRỊ GÓI KHÁM (VND)",
        align=WD_ALIGN_PARAGRAPH.CENTER,
        bold=True,
        size=10.5,
        color="FFFFFF",
        shading="2F5AA8",
    )
    grand = totals["grand_total_display"] or "0"
    merged_value = tr.cells[3].merge(tr.cells[5])
    
    # ép width cho phần value
    _set_cell_width(
        merged_value,
        widths_cm[3] + widths_cm[4] + widths_cm[5]
    )
    _write_cell_text(
        merged_value,
        grand,
        align=WD_ALIGN_PARAGRAPH.CENTER,
        bold=True,
        size=11,
        color="FFFFFF",
        shading="2F5AA8",
    )
    _set_cell_vertical_center(merged)
    _set_cell_vertical_center(merged_value)
    
    return table


def _set_cell_vertical_center(cell):
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()

    v_align = tc_pr.find(qn("w:vAlign"))
    if v_align is None:
        v_align = OxmlElement("w:vAlign")
        tc_pr.append(v_align)

    v_align.set(qn("w:val"), "center")


def _inject_table_at_marker(doc: Document, payload: dict) -> bool:
    marker = _find_table_marker(doc)
    if not marker:
        return False

    kind = marker[0]
    if kind == "document":
        paragraph = marker[1]
        paragraph.text = paragraph.text.replace(QUOTATION_TABLE_MARKER, "").strip()
        table = doc.add_table(rows=1, cols=6)
        table._tbl.getparent().remove(table._tbl)
        paragraph._p.addnext(table._tbl)
        # build rows into moved table using lightweight proxy
        proxy = type("TableContainer", (), {"add_table": lambda self, rows, cols: table})()
        _append_quotation_table(proxy, payload)
        if not paragraph.text.strip():
            _remove_paragraph(paragraph)
        return True

    if kind == "cell":
        cell, paragraph = marker[1], marker[2]
        paragraph.text = paragraph.text.replace(QUOTATION_TABLE_MARKER, "").strip()
        _clear_cell(cell)
        _append_quotation_table(cell, payload)
        return True

    return False


def create_default_quotation_docx(payload: dict, output_path: str):
    quotation = payload["quotation"]
    totals = payload["totals"]

    doc = Document()
    section = doc.sections[0]
    section.top_margin = Cm(1.7)
    section.bottom_margin = Cm(1.7)
    section.left_margin = Cm(1.25)
    section.right_margin = Cm(1.25)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run("BẢNG BÁO GIÁ KHÁM SỨC KHỎE")
    _style_runs(p, bold=True, size=20, color="2F5AA8")
    _set_paragraph_spacing(p, after=4)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run("PROPOSAL - Medical Check-up")
    _style_runs(p, bold=True, italic=True, size=16, color="F28C38")
    _set_paragraph_spacing(p, after=8)

    for line in [
        f"Kính gửi: {quotation['contact_name']}",
        f"Công ty: {quotation['company_name']}",
        f"Địa chỉ: {quotation['company_address']}",
        f"Giá ưu đãi áp dụng cho số lượng khám dự kiến từ: {quotation['pax_from'] or '___'} người",
        f"Hiệu lực đến: {quotation['valid_until_display'] or ''}",
    ]:
        p = doc.add_paragraph(line)
        _style_runs(p, size=11)
        _set_paragraph_spacing(p, after=2)

    p = doc.add_paragraph()
    p.add_run("Ghi chú: ").bold = True
    p.add_run(quotation["note"] or "")
    _style_runs(p, size=10.5)
    _set_paragraph_spacing(p, after=8)

    _append_quotation_table(doc, payload)

    p = doc.add_paragraph()
    p.add_run("Tổng Nam: ").bold = True
    p.add_run(totals["total_male_display"] or "0")
    _style_runs(p, size=10.5)
    _set_paragraph_spacing(p, before=8, after=2)

    p = doc.add_paragraph()
    p.add_run("Tổng Nữ độc thân: ").bold = True
    p.add_run(totals["total_female_single_display"] or "0")
    _style_runs(p, size=10.5)
    _set_paragraph_spacing(p, after=2)

    p = doc.add_paragraph()
    p.add_run("Tổng Nữ gia đình: ").bold = True
    p.add_run(totals["total_female_family_display"] or "0")
    _style_runs(p, size=10.5)
    _set_paragraph_spacing(p, after=2)

    p = doc.add_paragraph()
    p.add_run("Tổng giá trị dự kiến: ").bold = True
    p.add_run(totals["grand_total_display"] or "0")
    _style_runs(p, size=11)
    _set_paragraph_spacing(p, after=4)

    doc.save(output_path)
    return output_path


def render_quotation_docx(*, payload: dict, output_path: str, template_path: str | None = None):
    if template_path:
        template_file = Path(template_path)
        if template_file.exists() and template_file.is_file():
            doc = Document(str(template_file))
            replacements = _build_replacements(payload)
            _replace_text_everywhere(doc, replacements)
            inserted = _inject_table_at_marker(doc, payload)
            if not inserted:
                doc.add_paragraph("")
                _append_quotation_table(doc, payload)
            doc.save(output_path)
            return output_path

    return create_default_quotation_docx(payload, output_path)
