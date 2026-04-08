from collections import OrderedDict
from decimal import Decimal
from pathlib import Path
from typing import Any
import json

from apps.contract.models.quotation import QuotationDraft


def _vi_date(d) -> str:
    """Trả 'ngày DD tháng MM năm YYYY' hoặc chuỗi rỗng."""
    if not d:
        return ""
    return f"ngày {d.day} tháng {d.month} năm {d.year}"


def _vi_date_short(d) -> str:
    """Trả 'DD/MM/YYYY' hoặc chuỗi rỗng."""
    if not d:
        return ""
    return d.strftime("%d/%m/%Y")


def _vi_time(t) -> str:
    """Trả 'HH giờ MM phút' hoặc chuỗi rỗng."""
    if not t:
        return ""
    if t.minute:
        return f"{t.hour} giờ {t.minute:02d} phút"
    return f"{t.hour} giờ 00"


def _to_int(value: Any) -> int:
    if value in (None, "", False):
        return 0
    if isinstance(value, Decimal):
        return int(value)
    try:
        return int(value)
    except Exception:
        try:
            return int(str(value).replace(",", "").replace(".", ""))
        except Exception:
            return 0


def fmt_vnd(value: Any) -> str:
    return f"{_to_int(value):,}".replace(",", ".")


def _price_label_for_line(line_dict: dict) -> str:
    price_type = line_dict.get("price_type") or "standard"
    if price_type == "free":
        return line_dict.get("note") or "Miễn phí"
    if price_type == "gift":
        return line_dict.get("note") or "TẶNG"
    for key in ("price_male", "price_female_single", "price_female_family"):
        if line_dict.get(key):
            return fmt_vnd(line_dict[key])
    return ""


def _check_label(enabled: bool, price_type: str, note: str | None = None, discount_pct: float = 0) -> str:
    if not enabled:
        return "–"
    if price_type == "free":
        return note or "Miễn phí"
    if price_type == "gift":
        return note or "TẶNG"
    if discount_pct:
        pct_str = f"{discount_pct:g}"
        return f"✓\n(–{pct_str}%)"
    return "✓"


def _load_catalog_price_map() -> dict[int, dict]:
    base_dir = Path(__file__).resolve().parent.parent
    catalog_path = base_dir / "static" / "contract" / "data" / "catalog.json"

    if not catalog_path.exists():
        return {}

    try:
        with open(catalog_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        return {}

    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        items = raw.get("catalog") or raw.get("items") or []
    else:
        items = []

    result = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        item_id = item.get("id")
        if item_id is None:
            continue
        try:
            result[int(item_id)] = item
        except Exception:
            continue
    return result


def _build_contract_price_summary(profile, lines: list[dict]) -> dict:
    quotation = getattr(profile, "quotation", None)
    quotation_lines_by_id = {}

    if quotation:
        quotation_lines_by_id = {
            q.id: q for q in quotation.lines.order_by("display_order", "id")
        }

    base_total_male = 0
    base_total_fs = 0
    base_total_ff = 0

    discounted_unit_male = 0
    discounted_unit_fs = 0
    discounted_unit_ff = 0

    for line in lines:
        source_line = quotation_lines_by_id.get(line.get("source_quotation_line_id"))

        if line.get("for_male"):
            discounted_unit_male += _to_int(line.get("price_male"))
            base_total_male += _to_int(
                getattr(source_line, "price_male", None) if source_line else line.get("price_male")
            )

        if line.get("for_female_single"):
            discounted_unit_fs += _to_int(line.get("price_female_single"))
            base_total_fs += _to_int(
                getattr(source_line, "price_female_single", None) if source_line else line.get("price_female_single")
            )

        if line.get("for_female_family"):
            discounted_unit_ff += _to_int(line.get("price_female_family"))
            base_total_ff += _to_int(
                getattr(source_line, "price_female_family", None) if source_line else line.get("price_female_family")
            )

    male_count = _to_int(profile.male_count)
    female_single_count = _to_int(profile.female_single_count)
    female_family_count = _to_int(profile.female_family_count)

    grand_total = (
        discounted_unit_male * male_count
        + discounted_unit_fs * female_single_count
        + discounted_unit_ff * female_family_count
    )

    return {
        "base_total_male": base_total_male,
        "base_total_female_single": base_total_fs,
        "base_total_female_family": base_total_ff,
        "discounted_unit_male": discounted_unit_male,
        "discounted_unit_female_single": discounted_unit_fs,
        "discounted_unit_female_family": discounted_unit_ff,
        "grand_total_raw": grand_total,
        "base_total_male_display": fmt_vnd(base_total_male) if base_total_male else "",
        "base_total_female_single_display": fmt_vnd(base_total_fs) if base_total_fs else "",
        "base_total_female_family_display": fmt_vnd(base_total_ff) if base_total_ff else "",
        "discounted_unit_male_display": fmt_vnd(discounted_unit_male) if discounted_unit_male else "",
        "discounted_unit_female_single_display": fmt_vnd(discounted_unit_fs) if discounted_unit_fs else "",
        "discounted_unit_female_family_display": fmt_vnd(discounted_unit_ff) if discounted_unit_ff else "",
        "grand_total_display": fmt_vnd(grand_total) if grand_total else "",
    }


def build_quotation_document_payload(quotation: QuotationDraft) -> dict:
    raw_lines = list(quotation.lines.order_by("display_order", "id"))
    catalog_price_map = _load_catalog_price_map()
    
    lines = []
    for idx, line in enumerate(raw_lines, start=1):
        line_data = {
            "id": line.id,
            "stt": idx,
            "catalog_id": line.catalog_id,
            "item_name": line.item_name,
            "description": line.description or "",
            "group_name": line.group_name or "Khác",
            "subgroup_name": line.subgroup_name or "",
            "price_male": _to_int(line.price_male),
            "price_female_single": _to_int(line.price_female_single),
            "price_female_family": _to_int(line.price_female_family),
            "udai_price_male": _to_int(line.udai_price_male),
            "udai_price_fs": _to_int(line.udai_price_fs),
            "udai_price_ff": _to_int(line.udai_price_ff),
            "discount_male_pct": float(line.discount_male_pct or 0),
            "discount_fs_pct": float(line.discount_fs_pct or 0),
            "discount_ff_pct": float(line.discount_ff_pct or 0),
            "list_price": _to_int(line.list_price),
            "checked_male": bool(line.checked_male),
            "checked_female_single": bool(line.checked_female_single),
            "checked_female_family": bool(line.checked_female_family),
            "price_type": line.price_type or "standard",
            "note": line.note or "",
            "display_order": line.display_order,
        }
        line_data["display_unit_price"] = _price_label_for_line(line_data)
        line_data["male_mark"] = _check_label(
            line_data["checked_male"],
            line_data["price_type"],
            line_data["note"],
            discount_pct=line_data["discount_male_pct"],
        )
        line_data["female_single_mark"] = _check_label(
            line_data["checked_female_single"],
            line_data["price_type"],
            line_data["note"],
            discount_pct=line_data["discount_fs_pct"],
        )
        line_data["female_family_mark"] = _check_label(
            line_data["checked_female_family"],
            line_data["price_type"],
            line_data["note"],
            discount_pct=line_data["discount_ff_pct"],
        )
        lines.append(line_data)

    grouped = OrderedDict()
    display_rows = []

    for line in lines:
        group_name = line["group_name"] or "Khác"
        subgroup_name = line["subgroup_name"] or ""

        if group_name not in grouped:
            grouped[group_name] = {
                "items": [],
                "subgroups": OrderedDict(),
            }
            display_rows.append(
                {
                    "row_type": "group",
                    "label": group_name,
                }
            )

        if subgroup_name:
            if subgroup_name not in grouped[group_name]["subgroups"]:
                grouped[group_name]["subgroups"][subgroup_name] = []
                display_rows.append(
                    {
                        "row_type": "subgroup",
                        "label": subgroup_name,
                        "group_name": group_name,
                    }
                )
            grouped[group_name]["subgroups"][subgroup_name].append(line)
        else:
            grouped[group_name]["items"].append(line)

        display_rows.append(
            {
                "row_type": "item",
                "group_name": group_name,
                "subgroup_name": subgroup_name,
                "line": line,
            }
        )
    
    
    # ── Tổng giá gốc/người từ catalog.json ────────────────────────────────
    base_total_male = 0
    base_total_female_single = 0
    base_total_female_family = 0

    for line in lines:
        catalog_item = catalog_price_map.get(_to_int(line.get("catalog_id")))
        if not catalog_item:
            continue

        if line["checked_male"]:
            base_total_male += _to_int(catalog_item.get("price_male"))

        if line["checked_female_single"]:
            base_total_female_single += _to_int(catalog_item.get("price_female_single"))

        if line["checked_female_family"]:
            base_total_female_family += _to_int(catalog_item.get("price_female_family"))

    # ── Tổng giá ưu đãi/người từ line đã tính % giảm ─────────────────────
    discounted_total_male = sum(line["price_male"] for line in lines if line["checked_male"])
    discounted_total_female_single = sum(
        line["price_female_single"] for line in lines if line["checked_female_single"]
    )
    discounted_total_female_family = sum(
        line["price_female_family"] for line in lines if line["checked_female_family"]
    )

    grand_total = (
        discounted_total_male * _to_int(quotation.male_count)
        + discounted_total_female_single * _to_int(quotation.female_single_count)
        + discounted_total_female_family * _to_int(quotation.female_family_count)
    )
    
    total_male = sum(line["price_male"] for line in lines if line["checked_male"])
    total_female_single = sum(line["price_female_single"] for line in lines if line["checked_female_single"])
    total_female_family = sum(line["price_female_family"] for line in lines if line["checked_female_family"])

    payload = {
        "quotation": {
            "id": quotation.id,
            "contact_name": quotation.contact_name or "",
            "company_name": quotation.company_name or "",
            "company_address": quotation.company_address or "",
            "valid_until": quotation.valid_until.isoformat() if quotation.valid_until else "",
            "valid_until_display": quotation.valid_until.strftime("%d/%m/%Y") if quotation.valid_until else "",
            "pax_from": quotation.pax_from or "",
            "male_count": _to_int(quotation.male_count),
            "female_single_count": _to_int(quotation.female_single_count),
            "female_family_count": _to_int(quotation.female_family_count),
            "note": quotation.note or "",
            "discount_male_pct": float(quotation.discount_male_pct or 0),
            "discount_fs_pct": float(quotation.discount_fs_pct or 0),
            "discount_ff_pct": float(quotation.discount_ff_pct or 0),
            "created_at": quotation.created_at.isoformat() if quotation.created_at else "",
            "updated_at": quotation.updated_at.isoformat() if quotation.updated_at else "",
        },
        "lines": lines,
        "grouped": grouped,
        "display_rows": display_rows,
        "totals": {
            "base_total_male": base_total_male,
            "base_total_female_single": base_total_female_single,
            "base_total_female_family": base_total_female_family,

            "discounted_total_male": discounted_total_male,
            "discounted_total_female_single": discounted_total_female_single,
            "discounted_total_female_family": discounted_total_female_family,

            "grand_total": grand_total,

            "base_total_male_display": fmt_vnd(base_total_male) if base_total_male else "",
            "base_total_female_single_display": fmt_vnd(base_total_female_single) if base_total_female_single else "",
            "base_total_female_family_display": fmt_vnd(base_total_female_family) if base_total_female_family else "",

            "discounted_total_male_display": fmt_vnd(discounted_total_male) if discounted_total_male else "",
            "discounted_total_female_single_display": fmt_vnd(discounted_total_female_single) if discounted_total_female_single else "",
            "discounted_total_female_family_display": fmt_vnd(discounted_total_female_family) if discounted_total_female_family else "",

            "total_male_display": fmt_vnd(discounted_total_male) if discounted_total_male else "",
            "total_female_single_display": fmt_vnd(discounted_total_female_single) if discounted_total_female_single else "",
            "total_female_family_display": fmt_vnd(discounted_total_female_family) if discounted_total_female_family else "",

            "grand_total_display": fmt_vnd(grand_total) if grand_total else "",
        },
    }
    return payload


def build_quotation_preview_context(quotation: QuotationDraft) -> dict:
    payload = build_quotation_document_payload(quotation)
    totals = payload["totals"]

    return {
        "quotation_payload": payload,
        "lines": payload["lines"],
        "grouped": payload["grouped"],
        "display_rows": payload["display_rows"],

        "base_total_male": totals["base_total_male"],
        "base_total_female_single": totals["base_total_female_single"],
        "base_total_female_family": totals["base_total_female_family"],

        "discounted_total_male": totals["discounted_total_male"],
        "discounted_total_female_single": totals["discounted_total_female_single"],
        "discounted_total_female_family": totals["discounted_total_female_family"],

        # giữ tương thích template cũ nếu còn chỗ dùng
        "total_male": totals["discounted_total_male"],
        "total_female_single": totals["discounted_total_female_single"],
        "total_female_family": totals["discounted_total_female_family"],

        "grand_total": totals["grand_total"],
        "fmt_vnd": fmt_vnd,
    }


def build_contract_document_payload(contract) -> dict:
    """
    Snapshot payload cho:
      1) Lưu vào IssuedDocument.payload_json
      2) Render DOCX/PDF/HTML preview của hợp đồng

    Nguồn dữ liệu chuẩn duy nhất cho phần line của hợp đồng là:
        contract.service_lines
    """
    profile = contract.corporate_profile

    # ── Lịch lấy máu ────────────────────────────────────────────────────────
    blood_rows = []
    for row in contract.blood_collection_schedules.order_by("collection_date", "id"):
        blood_rows.append(
            {
                "collection_date": row.collection_date.isoformat() if row.collection_date else "",
                "collection_date_vi": _vi_date(row.collection_date),
                "collection_date_short": _vi_date_short(row.collection_date),
                "location": row.location or "",
                "people_count": row.people_count,
                "staff_count": row.staff_count,
                "note": row.note or "",
            }
        )

    # ── Danh mục dịch vụ từ contract lines ─────────────────────────────────
    raw_lines = list(contract.service_lines.order_by("display_order", "id"))
    lines = []

    for idx, line in enumerate(raw_lines, start=1):
        line_data = {
            "id": line.id,
            "stt": idx,
            "source_quotation_line_id": getattr(line, "source_quotation_line_id", None),
            "catalog_service_id": getattr(line, "catalog_service_id", None),
            "item_name": line.item_name,
            "description": line.description or "",
            "group_name": line.group_name or "Khác",
            "subgroup_name": getattr(line, "subgroup_name", "") or "",
            "group_name_en": getattr(line, "group_name_en", "") or "",
            "price_male": _to_int(line.price_male),
            "price_female_single": _to_int(line.price_female_single),
            "price_female_family": _to_int(line.price_female_family),
            "for_male": bool(line.for_male),
            "for_female_single": bool(line.for_female_single),
            "for_female_family": bool(line.for_female_family),
            "price_type": getattr(line, "price_type", "standard") or "standard",
            "note": line.note or "",
            "display_order": line.display_order,
        }
        line_data["display_unit_price"] = _price_label_for_line(line_data)
        lines.append(line_data)

    grouped = OrderedDict()
    display_rows = []

    for line in lines:
        group_name = line["group_name"] or "Khác"
        subgroup_name = line["subgroup_name"] or ""

        if group_name not in grouped:
            grouped[group_name] = {
                "items": [],
                "subgroups": OrderedDict(),
            }
            display_rows.append(
                {
                    "row_type": "group",
                    "label": group_name,
                }
            )

        if subgroup_name:
            if subgroup_name not in grouped[group_name]["subgroups"]:
                grouped[group_name]["subgroups"][subgroup_name] = []
                display_rows.append(
                    {
                        "row_type": "subgroup",
                        "label": subgroup_name,
                        "group_name": group_name,
                    }
                )
            grouped[group_name]["subgroups"][subgroup_name].append(line)
        else:
            grouped[group_name]["items"].append(line)

        display_rows.append(
            {
                "row_type": "item",
                "group_name": group_name,
                "subgroup_name": subgroup_name,
                "line": line,
            }
        )
    
    # ── Tính toán tài chính ────────────────────────────────────────────────
    price_summary = _build_contract_price_summary(profile, lines)
    
    subtotal_male = price_summary["discounted_unit_male"]
    subtotal_fs = price_summary["discounted_unit_female_single"]
    subtotal_ff = price_summary["discounted_unit_female_family"]
    grand_total = price_summary["grand_total_raw"] or _to_int(profile.grand_total)
    
    deposit_pct = float(profile.deposit_pct or 30)
    deposit_amount = _to_int(profile.deposit_amount) or int(grand_total * deposit_pct / 100)
    settlement_days = profile.settlement_days or 10

    # ── Số hợp đồng & ngày tháng ───────────────────────────────────────────
    from datetime import date as date_cls
    
    issue_date = profile.contract_date or date_cls.today()
    year = issue_date.year
    
    contract_number = contract.contract_number or ""
    contract_number_full = contract_number if contract_number else f"<___>/HĐKD-VMD/<{year}>"

    # ── Thời gian thực hiện hợp đồng ───────────────────────────────────────
    start_date_vi = _vi_date_short(contract.start_date)
    end_date_vi = _vi_date_short(contract.end_date)
    period_text = ""
    if contract.start_date and contract.end_date:
        period_text = f"{start_date_vi} - {end_date_vi}"
    elif contract.start_date:
        period_text = f"Từ {start_date_vi}"

    reception_date_vi = _vi_date_short(contract.reception_from_date)

    # ── Giờ lấy máu ────────────────────────────────────────────────────────
    blood_collection_from_at = getattr(profile, "blood_collection_from_at", None)
    blood_collection_to_at = getattr(profile, "blood_collection_to_at", None)
    
    blood_time_from = _vi_time(profile.blood_collection_time_from)
    blood_time_to = _vi_time(profile.blood_collection_time_to)
    
    blood_collection_from_text = _vi_date_short(blood_collection_from_at.date()) if blood_collection_from_at else ""
    blood_collection_to_text = _vi_date_short(blood_collection_to_at.date()) if blood_collection_to_at else ""
    
    blood_time_text = ""
    if blood_collection_from_at and blood_collection_to_at:
        blood_time_text = (
            f"Từ {_vi_date_short(blood_collection_from_at.date())} "
            f"{blood_collection_from_at.strftime('%H:%M')} "
            f"đến {_vi_date_short(blood_collection_to_at.date())} "
            f"{blood_collection_to_at.strftime('%H:%M')}"
        )
    elif blood_collection_from_at:
        blood_time_text = (
            f"Từ {_vi_date_short(blood_collection_from_at.date())} "
            f"{blood_collection_from_at.strftime('%H:%M')}"
        )
    elif blood_time_from and blood_time_to:
        blood_time_text = f"Từ {blood_time_from} đến {blood_time_to}"
    elif blood_time_from:
        blood_time_text = f"Từ {blood_time_from}"

    # ── Thông tin đặt cọc ──────────────────────────────────────────────────
    deposit_deadline_vi = _vi_date_short(profile.deposit_deadline)
    deposit_pct_display = f"{deposit_pct:g}%"
    deposit_amount_words = (getattr(profile, "deposit_amount_words", None) or "").strip()

    payload = {
        # Header
        "contract_number": contract_number,
        "contract_number_full": contract_number_full,
        "issue_day": str(issue_date.day),
        "issue_month": str(issue_date.month),
        "issue_year": str(issue_date.year),
        "issue_date": _vi_date_short(issue_date),
        "issue_date_vi": _vi_date(issue_date),

        # Bên B
        "company_name": profile.company_name_snapshot or "",
        "company_address": profile.company_address_snapshot or "",
        "company_phone": profile.company_phone_snapshot or "",
        "company_tax_code": profile.company_tax_code_snapshot or "",
        "contact_person": profile.contact_person_snapshot or contract.contact_person or "",
        "representative_title": profile.representative_title_snapshot or contract.representative_title or "",
        "signer_b_name": profile.signer_b_name or "",
        "signer_b_title": profile.signer_b_title or "",

        # Bên A
        "signer_a_name": profile.signer_a_name or "TS.BS. PHẠM THẾ VIỆT",
        "signer_a_title": profile.signer_a_title or "Tổng Giám Đốc",

        # Điều I
        "start_date": start_date_vi,
        "end_date": end_date_vi,
        "period_text": period_text,
        "reception_from_date": reception_date_vi,
        "blood_time_from": blood_time_from,
        "blood_time_to": blood_time_to,
        "blood_time_text": blood_time_text,
        "blood_collection_location": profile.blood_collection_location or "",
        "blood_collection_from_text": blood_collection_from_text,
        "blood_collection_to_text": blood_collection_to_text,

        # Nhân sự
        "male_count": profile.male_count or 0,
        "female_single_count": profile.female_single_count or 0,
        "female_family_count": profile.female_family_count or 0,
        "total_pax": (profile.male_count or 0)
        + (profile.female_single_count or 0)
        + (profile.female_family_count or 0),

        # Tài chính
                "base_total_male": price_summary["base_total_male"],
        "base_total_female_single": price_summary["base_total_female_single"],
        "base_total_female_family": price_summary["base_total_female_family"],
        "base_total_male_display": price_summary["base_total_male_display"],
        "base_total_female_single_display": price_summary["base_total_female_single_display"],
        "base_total_female_family_display": price_summary["base_total_female_family_display"],

        "subtotal_male": price_summary["discounted_unit_male_display"],
        "subtotal_female_single": price_summary["discounted_unit_female_single_display"],
        "subtotal_female_family": price_summary["discounted_unit_female_family_display"],

        "discounted_unit_male": price_summary["discounted_unit_male"],
        "discounted_unit_female_single": price_summary["discounted_unit_female_single"],
        "discounted_unit_female_family": price_summary["discounted_unit_female_family"],
        "discounted_unit_male_display": price_summary["discounted_unit_male_display"],
        "discounted_unit_female_single_display": price_summary["discounted_unit_female_single_display"],
        "discounted_unit_female_family_display": price_summary["discounted_unit_female_family_display"],

        "grand_total": price_summary["grand_total_display"],
        "grand_total_raw": grand_total,
        "deposit_pct": deposit_pct_display,
        "deposit_amount": fmt_vnd(deposit_amount),
        "deposit_deadline": deposit_deadline_vi,
        "deposit_amount_words": deposit_amount_words,
        "settlement_days": str(settlement_days),

        # Ghi chú
        "contract_note": profile.contract_note or "",
        "quotation_note": profile.quotation_note or "",
        "note": contract.note or "",

        # Dữ liệu line / lịch lấy máu
        "lines": lines,
        "grouped": grouped,
        "display_rows": display_rows,
        "blood_rows": blood_rows,
    }

    return payload


def build_contract_preview_context(contract) -> dict:
    payload = build_contract_document_payload(contract)
    return {
        "contract": contract,
        "contract_payload": payload,
        "lines": payload["lines"],
        "grouped": payload["grouped"],
        "display_rows": payload["display_rows"],
        "blood_rows": payload["blood_rows"],
        "fmt_vnd": fmt_vnd,
    }