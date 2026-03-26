#===== preview HTML, DOCX render, PDF render dùng payload ===
from collections import OrderedDict
from decimal import Decimal
from typing import Any

from apps.contract.models.quotation import QuotationDraft


def _to_int(value: Any) -> int:
    if value in (None, "", False):
        return 0
    if isinstance(value, Decimal):
        return int(value)
    return int(value)


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
        pct_str = f"{discount_pct:g}"          # 20.0 → "20", 2.5 → "2.5"
        return f"✓\n(–{pct_str}%)"
    return "✓"


def build_quotation_document_payload(quotation: QuotationDraft) -> dict:
    raw_lines = list(quotation.lines.order_by("display_order", "id"))

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

    total_male = sum(line["price_male"] for line in lines if line["checked_male"])
    total_female_single = sum(line["price_female_single"] for line in lines if line["checked_female_single"])
    total_female_family = sum(line["price_female_family"] for line in lines if line["checked_female_family"])

    grand_total = (
        total_male * _to_int(quotation.male_count)
        + total_female_single * _to_int(quotation.female_single_count)
        + total_female_family * _to_int(quotation.female_family_count)
    )

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
            "total_male": total_male,
            "total_female_single": total_female_single,
            "total_female_family": total_female_family,
            "grand_total": grand_total,
            "total_male_display": fmt_vnd(total_male) if total_male else "",
            "total_female_single_display": fmt_vnd(total_female_single) if total_female_single else "",
            "total_female_family_display": fmt_vnd(total_female_family) if total_female_family else "",
            "grand_total_display": fmt_vnd(grand_total) if grand_total else "",
        },
    }
    return payload


def build_quotation_preview_context(quotation: QuotationDraft) -> dict:
    payload = build_quotation_document_payload(quotation)
    return {
        "quotation_payload": payload,
        "lines": payload["lines"],
        "grouped": payload["grouped"],
        "display_rows": payload["display_rows"],
        "total_male": payload["totals"]["total_male"],
        "total_female_single": payload["totals"]["total_female_single"],
        "total_female_family": payload["totals"]["total_female_family"],
        "grand_total": payload["totals"]["grand_total"],
        "fmt_vnd": fmt_vnd,
    }