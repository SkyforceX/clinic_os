from collections import OrderedDict
from decimal import Decimal
from pathlib import Path
from typing import Any
import json

from apps.contract.models.quotation import QuotationDraft, STANDARD_COL_KEYS


def _vi_date(d) -> str:
    if not d:
        return ""
    return f"ngày {d.day} tháng {d.month} năm {d.year}"


def _vi_date_short(d) -> str:
    if not d:
        return ""
    return d.strftime("%d/%m/%Y")


def _vi_time(t) -> str:
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


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _build_quotation_company_payload(quotation: QuotationDraft) -> dict:
    company = getattr(quotation, "company", None)
    company_name = _safe_text(getattr(quotation, "company_name", "")) or _safe_text(getattr(company, "name", ""))
    company_address = _safe_text(getattr(quotation, "company_address", "")) or _safe_text(getattr(company, "address", ""))
    company_phone = _safe_text(getattr(quotation, "contact_phone", "")) or _safe_text(getattr(company, "phone", ""))
    company_tax_code = _safe_text(getattr(quotation, "tax_code", "")) or _safe_text(getattr(company, "tax_code", ""))
    return {
        "company_name": company_name,
        "company_address": company_address,
        "contact_phone": company_phone,
        "company_phone": company_phone,
        "phone": company_phone,
        "tax_code": company_tax_code,
        "company_tax_code": company_tax_code,
        "mst": company_tax_code,
    }


def _price_label_for_line(line_dict: dict) -> str:
    price_type = (line_dict.get("price_type") or "standard").strip().lower()
    note = (line_dict.get("note") or "").strip()

    if price_type == "free":
        return note or "Miễn phí"
    if price_type == "gift":
        return note or "TẶNG"

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


def _build_line_dict(idx: int, line, catalog_price_map: dict) -> dict:
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
        "extra_prices_json": line.extra_prices_json or {},
    }
    line_data["has_discount_male"] = bool(line_data["checked_male"] and line_data["discount_male_pct"] > 0)
    line_data["has_discount_female_single"] = bool(
        line_data["checked_female_single"] and line_data["discount_fs_pct"] > 0
    )
    line_data["has_discount_female_family"] = bool(
        line_data["checked_female_family"] and line_data["discount_ff_pct"] > 0
    )
    line_data["has_any_discount"] = bool(
        line_data["has_discount_male"]
        or line_data["has_discount_female_single"]
        or line_data["has_discount_female_family"]
    )
    line_data["display_unit_price"] = _price_label_for_line(line_data)
    line_data["male_mark"] = _check_label(
        line_data["checked_male"], line_data["price_type"], line_data["note"],
        discount_pct=line_data["discount_male_pct"],
    )
    line_data["female_single_mark"] = _check_label(
        line_data["checked_female_single"], line_data["price_type"], line_data["note"],
        discount_pct=line_data["discount_fs_pct"],
    )
    line_data["female_family_mark"] = _check_label(
        line_data["checked_female_family"], line_data["price_type"], line_data["note"],
        discount_pct=line_data["discount_ff_pct"],
    )
    return line_data


def _build_display_rows(lines: list[dict]) -> tuple[OrderedDict, list[dict]]:
    grouped = OrderedDict()
    display_rows = []
    for line in lines:
        group_name = line["group_name"] or "Khác"
        subgroup_name = line["subgroup_name"] or ""
        if group_name not in grouped:
            grouped[group_name] = {"items": [], "subgroups": OrderedDict()}
            display_rows.append({"row_type": "group", "label": group_name})
        if subgroup_name:
            if subgroup_name not in grouped[group_name]["subgroups"]:
                grouped[group_name]["subgroups"][subgroup_name] = []
                display_rows.append({"row_type": "subgroup", "label": subgroup_name, "group_name": group_name})
            grouped[group_name]["subgroups"][subgroup_name].append(line)
        else:
            grouped[group_name]["items"].append(line)
        display_rows.append({"row_type": "item", "group_name": group_name, "subgroup_name": subgroup_name, "line": line})
    return grouped, display_rows


def _resolve_quotation_standard_base_price(line_data: dict, key: str, catalog_price_map: dict) -> int:
    catalog_item = catalog_price_map.get(_to_int(line_data.get("catalog_id"))) or {}

    if key == "male":
        candidates = [
            catalog_item.get("price_male"),
            line_data.get("list_price"),
            line_data.get("udai_price_male"),
            line_data.get("price_male"),
        ]
    elif key == "female_single":
        candidates = [
            catalog_item.get("price_female_single"),
            line_data.get("list_price"),
            line_data.get("udai_price_fs"),
            line_data.get("price_female_single"),
        ]
    else:
        candidates = [
            catalog_item.get("price_female_family"),
            line_data.get("list_price"),
            line_data.get("udai_price_ff"),
            line_data.get("price_female_family"),
        ]

    return max(_to_int(value) for value in candidates)


def _build_package_totals(columns_json: list, lines: list[dict], catalog_price_map: dict) -> dict:
    """Tính totals cho một gói khám dựa trên columns_json."""
    totals_by_col = {}
    for col in columns_json:
        key = col.get("key", "")
        count = _to_int(col.get("count") or 0)
        label = col.get("label", key)

        if key == "male":
            per_person = sum(ld["price_male"] for ld in lines if ld["checked_male"])
            base_per_person = sum(
                _resolve_quotation_standard_base_price(ld, "male", catalog_price_map)
                for ld in lines if ld["checked_male"]
            )
        elif key == "female_single":
            per_person = sum(ld["price_female_single"] for ld in lines if ld["checked_female_single"])
            base_per_person = sum(
                _resolve_quotation_standard_base_price(ld, "female_single", catalog_price_map)
                for ld in lines if ld["checked_female_single"]
            )
        elif key == "female_family":
            per_person = sum(ld["price_female_family"] for ld in lines if ld["checked_female_family"])
            base_per_person = sum(
                _resolve_quotation_standard_base_price(ld, "female_family", catalog_price_map)
                for ld in lines if ld["checked_female_family"]
            )
        else:
            per_person = sum(
                _to_int((ld.get("extra_prices_json") or {}).get(key) or 0)
                for ld in lines
            )
            base_per_person = sum(
                _to_int(
                    (ld.get("extra_prices_json") or {}).get(f"{key}_udai")
                    or (ld.get("extra_prices_json") or {}).get(key)
                    or 0
                )
                for ld in lines
            )

        subtotal = per_person * count
        base_subtotal = base_per_person * count

        totals_by_col[key] = {
            "key": key,
            "label": label,
            "count": count,
            "per_person": per_person,
            "base_per_person": base_per_person,
            "per_person_display": fmt_vnd(per_person) if per_person else "",
            "base_per_person_display": fmt_vnd(base_per_person) if base_per_person else "",
            "subtotal": subtotal,
            "subtotal_display": fmt_vnd(subtotal) if subtotal else "",
            "base_subtotal": base_subtotal,
            "base_subtotal_display": fmt_vnd(base_subtotal) if base_subtotal else "",
        }

    grand = sum(v["subtotal"] for v in totals_by_col.values())
    base_grand = sum(v["base_subtotal"] for v in totals_by_col.values())

    return {
        "by_col": totals_by_col,
        "grand_total": grand,
        "grand_total_display": fmt_vnd(grand) if grand else "",
        "base_grand_total": base_grand,
        "base_grand_total_display": fmt_vnd(base_grand) if base_grand else "",

        # standard compat
        "discounted_total_male": totals_by_col.get("male", {}).get("per_person", 0),
        "discounted_total_female_single": totals_by_col.get("female_single", {}).get("per_person", 0),
        "discounted_total_female_family": totals_by_col.get("female_family", {}).get("per_person", 0),
        "discounted_total_male_display": totals_by_col.get("male", {}).get("per_person_display", ""),
        "discounted_total_female_single_display": totals_by_col.get("female_single", {}).get("per_person_display", ""),
        "discounted_total_female_family_display": totals_by_col.get("female_family", {}).get("per_person_display", ""),

        "base_total_male": totals_by_col.get("male", {}).get("base_per_person", 0),
        "base_total_female_single": totals_by_col.get("female_single", {}).get("base_per_person", 0),
        "base_total_female_family": totals_by_col.get("female_family", {}).get("base_per_person", 0),
        "base_total_male_display": totals_by_col.get("male", {}).get("base_per_person_display", ""),
        "base_total_female_single_display": totals_by_col.get("female_single", {}).get("base_per_person_display", ""),
        "base_total_female_family_display": totals_by_col.get("female_family", {}).get("base_per_person_display", ""),
    }


def build_quotation_document_payload(quotation: QuotationDraft) -> dict:
    catalog_price_map = _load_catalog_price_map()
    packages_qs = list(quotation.packages.prefetch_related("lines").order_by("display_order", "id"))

    # ── MULTI-PACKAGE mode ────────────────────────────────────────────────────
    if packages_qs:
        packages_payload = []
        grand_total_all = 0

        for pkg in packages_qs:
            pkg_lines_raw = list(pkg.lines.order_by("display_order", "id"))
            pkg_lines = [_build_line_dict(i + 1, l, catalog_price_map) for i, l in enumerate(pkg_lines_raw)]
            grouped, display_rows = _build_display_rows(pkg_lines)
            pkg_totals = _build_package_totals(pkg.columns_json or [], pkg_lines, catalog_price_map)
            grand_total_all += pkg_totals["grand_total"]

            packages_payload.append({
                "id": pkg.id,
                "name": pkg.name,
                "display_order": pkg.display_order,
                "columns_json": pkg.columns_json or [],
                "lines": pkg_lines,
                "grouped": grouped,
                "display_rows": display_rows,
                "totals": pkg_totals,
            })

        # Build flat lines for legacy compat (preview tabs, etc.)
        all_lines = []
        stt = 1
        for pkg in packages_qs:
            for l in pkg.lines.order_by("display_order", "id"):
                all_lines.append(_build_line_dict(stt, l, catalog_price_map))
                stt += 1
        all_grouped, all_display_rows = _build_display_rows(all_lines)

        payload = {
            "quotation": {
                "id": quotation.id,
                "contact_name": quotation.contact_name or "",
                **_build_quotation_company_payload(quotation),
                "valid_until": quotation.valid_until.isoformat() if quotation.valid_until else "",
                "valid_until_display": quotation.valid_until.strftime("%d/%m/%Y") if quotation.valid_until else "",
                "pax_from": quotation.pax_from or "",
                "note": quotation.note or "",
                "extra_content": quotation.extra_content or "",
                "discount_male_pct": float(quotation.discount_male_pct or 0),
                "discount_fs_pct": float(quotation.discount_fs_pct or 0),
                "discount_ff_pct": float(quotation.discount_ff_pct or 0),
                "created_at": quotation.created_at.isoformat() if quotation.created_at else "",
            },
            "packages": packages_payload,
            "multi_package": True,
            # Legacy compat
            "lines": all_lines,
            "grouped": all_grouped,
            "display_rows": all_display_rows,
            "totals": {
                "grand_total": grand_total_all,
                "grand_total_display": fmt_vnd(grand_total_all) if grand_total_all else "",

                "base_grand_total": sum(p["totals"].get("base_grand_total", 0) for p in packages_payload),
                "base_grand_total_display": fmt_vnd(
                    sum(p["totals"].get("base_grand_total", 0) for p in packages_payload)
                ) if sum(p["totals"].get("base_grand_total", 0) for p in packages_payload) else "",

                "base_total_male": sum(p["totals"]["base_total_male"] for p in packages_payload),
                "base_total_female_single": sum(p["totals"]["base_total_female_single"] for p in packages_payload),
                "base_total_female_family": sum(p["totals"]["base_total_female_family"] for p in packages_payload),

                "discounted_total_male": sum(p["totals"]["discounted_total_male"] for p in packages_payload),
                "discounted_total_female_single": sum(p["totals"]["discounted_total_female_single"] for p in packages_payload),
                "discounted_total_female_family": sum(p["totals"]["discounted_total_female_family"] for p in packages_payload),

                "base_total_male_display": fmt_vnd(sum(p["totals"]["base_total_male"] for p in packages_payload))
                    if sum(p["totals"]["base_total_male"] for p in packages_payload) else "",
                "base_total_female_single_display": fmt_vnd(sum(p["totals"]["base_total_female_single"] for p in packages_payload))
                    if sum(p["totals"]["base_total_female_single"] for p in packages_payload) else "",
                "base_total_female_family_display": fmt_vnd(sum(p["totals"]["base_total_female_family"] for p in packages_payload))
                    if sum(p["totals"]["base_total_female_family"] for p in packages_payload) else "",

                "discounted_total_male_display": fmt_vnd(sum(p["totals"]["discounted_total_male"] for p in packages_payload))
                    if sum(p["totals"]["discounted_total_male"] for p in packages_payload) else "",
                "discounted_total_female_single_display": fmt_vnd(sum(p["totals"]["discounted_total_female_single"] for p in packages_payload))
                    if sum(p["totals"]["discounted_total_female_single"] for p in packages_payload) else "",
                "discounted_total_female_family_display": fmt_vnd(sum(p["totals"]["discounted_total_female_family"] for p in packages_payload))
                    if sum(p["totals"]["discounted_total_female_family"] for p in packages_payload) else "",

                "total_male_display": fmt_vnd(sum(p["totals"]["discounted_total_male"] for p in packages_payload))
                    if sum(p["totals"]["discounted_total_male"] for p in packages_payload) else "",
                "total_female_single_display": fmt_vnd(sum(p["totals"]["discounted_total_female_single"] for p in packages_payload))
                    if sum(p["totals"]["discounted_total_female_single"] for p in packages_payload) else "",
                "total_female_family_display": fmt_vnd(sum(p["totals"]["discounted_total_female_family"] for p in packages_payload))
                    if sum(p["totals"]["discounted_total_female_family"] for p in packages_payload) else "",
            },
        }
        return payload

    # ── LEGACY single-package mode ─────────────────────────────────────────
    raw_lines = list(quotation.lines.order_by("display_order", "id"))
    lines = [_build_line_dict(i + 1, l, catalog_price_map) for i, l in enumerate(raw_lines)]
    grouped, display_rows = _build_display_rows(lines)

    base_total_male = 0
    base_total_female_single = 0
    base_total_female_family = 0
    for line in lines:
        if line["checked_male"]:
            base_total_male += _resolve_quotation_standard_base_price(line, "male", catalog_price_map)
        if line["checked_female_single"]:
            base_total_female_single += _resolve_quotation_standard_base_price(line, "female_single", catalog_price_map)
        if line["checked_female_family"]:
            base_total_female_family += _resolve_quotation_standard_base_price(line, "female_family", catalog_price_map)

    discounted_total_male = sum(l["price_male"] for l in lines if l["checked_male"])
    discounted_total_female_single = sum(l["price_female_single"] for l in lines if l["checked_female_single"])
    discounted_total_female_family = sum(l["price_female_family"] for l in lines if l["checked_female_family"])
    grand_total = (
        discounted_total_male * _to_int(quotation.male_count)
        + discounted_total_female_single * _to_int(quotation.female_single_count)
        + discounted_total_female_family * _to_int(quotation.female_family_count)
    )

    payload = {
        "quotation": {
            "id": quotation.id,
            "contact_name": quotation.contact_name or "",
            **_build_quotation_company_payload(quotation),
            "valid_until": quotation.valid_until.isoformat() if quotation.valid_until else "",
            "valid_until_display": quotation.valid_until.strftime("%d/%m/%Y") if quotation.valid_until else "",
            "pax_from": quotation.pax_from or "",
            "male_count": _to_int(quotation.male_count),
            "female_single_count": _to_int(quotation.female_single_count),
            "female_family_count": _to_int(quotation.female_family_count),
            "note": quotation.note or "",
            "extra_content": quotation.extra_content or "",
            "discount_male_pct": float(quotation.discount_male_pct or 0),
            "discount_fs_pct": float(quotation.discount_fs_pct or 0),
            "discount_ff_pct": float(quotation.discount_ff_pct or 0),
            "created_at": quotation.created_at.isoformat() if quotation.created_at else "",
        },
        "packages": [],
        "multi_package": False,
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
        "packages": payload.get("packages", []),
        "multi_package": payload.get("multi_package", False),
        "lines": payload["lines"],
        "grouped": payload["grouped"],
        "display_rows": payload["display_rows"],
        "base_total_male": totals.get("base_total_male", 0),
        "base_total_female_single": totals.get("base_total_female_single", 0),
        "base_total_female_family": totals.get("base_total_female_family", 0),
        "discounted_total_male": totals.get("discounted_total_male", 0),
        "discounted_total_female_single": totals.get("discounted_total_female_single", 0),
        "discounted_total_female_family": totals.get("discounted_total_female_family", 0),
        "total_male": totals.get("discounted_total_male", 0),
        "total_female_single": totals.get("discounted_total_female_single", 0),
        "total_female_family": totals.get("discounted_total_female_family", 0),
        "grand_total": totals.get("grand_total", 0),
        "fmt_vnd": fmt_vnd,
    }


def _build_contract_column_defs(profile, columns_json: list | None) -> list[dict]:
    """
    Chuẩn hoá cấu hình cột cho preview hợp đồng.
    - cột chuẩn: count lấy từ profile
    - cột custom: count lấy từ columns_json của package
    """
    columns = []
    for raw in (columns_json or []):
        key = str(raw.get("key") or "").strip()
        if not key:
            continue

        if key == "male":
            count = _to_int(getattr(profile, "male_count", 0))
            default_label = "NAM"
        elif key == "female_single":
            count = _to_int(getattr(profile, "female_single_count", 0))
            default_label = "NỮ ĐỘC THÂN"
        elif key == "female_family":
            count = _to_int(getattr(profile, "female_family_count", 0))
            default_label = "NỮ GIA ĐÌNH"
        else:
            count = _to_int(raw.get("count") or 0)
            default_label = key

        columns.append({
            "key": key,
            "label": (raw.get("label") or default_label).strip(),
            "count": count,
        })

    return columns


def _get_contract_custom_cell_mark(source_line, price_type: str, note: str, key: str) -> str:
    extra = getattr(source_line, "extra_prices_json", None) or {}
    has_key = key in extra or f"{key}_udai" in extra
    if not has_key:
        return "–"
    return _check_label(True, price_type, note)


def _get_contract_column_cell(line_data: dict, source_line, key: str) -> str:
    if key == "male":
        return line_data.get("male_mark") or "–"
    if key == "female_single":
        return line_data.get("female_single_mark") or "–"
    if key == "female_family":
        return line_data.get("female_family_mark") or "–"
    return _get_contract_custom_cell_mark(
        source_line=source_line,
        price_type=line_data.get("price_type") or "standard",
        note=line_data.get("note") or "",
        key=key,
    )


def _build_contract_line_column_cells(line_data: dict, source_line, columns: list[dict]) -> list[dict]:
    return [
        {
            "key": col["key"],
            "label": col["label"],
            "mark": _get_contract_column_cell(line_data, source_line, col["key"]),
        }
        for col in columns
    ]


def _get_contract_standard_prices(line_data: dict, source_line, key: str, catalog_price_map: dict) -> tuple[int, int]:
    catalog_id = getattr(source_line, "catalog_id", None) if source_line else None
    catalog_item = catalog_price_map.get(_to_int(catalog_id)) if catalog_id else None

    if key == "male":
        enabled = bool(line_data.get("for_male"))
        discounted = _to_int(line_data.get("price_male")) if enabled else 0
        if not enabled:
            return 0, 0
        if catalog_item:
            base = _to_int(catalog_item.get("price_male"))
        elif source_line:
            base = _to_int(getattr(source_line, "udai_price_male", None) or getattr(source_line, "price_male", None))
        else:
            base = discounted
        return discounted, base

    if key == "female_single":
        enabled = bool(line_data.get("for_female_single"))
        discounted = _to_int(line_data.get("price_female_single")) if enabled else 0
        if not enabled:
            return 0, 0
        if catalog_item:
            base = _to_int(catalog_item.get("price_female_single"))
        elif source_line:
            base = _to_int(getattr(source_line, "udai_price_fs", None) or getattr(source_line, "price_female_single", None))
        else:
            base = discounted
        return discounted, base

    enabled = bool(line_data.get("for_female_family"))
    discounted = _to_int(line_data.get("price_female_family")) if enabled else 0
    if not enabled:
        return 0, 0
    if catalog_item:
        base = _to_int(catalog_item.get("price_female_family"))
    elif source_line:
        base = _to_int(getattr(source_line, "udai_price_ff", None) or getattr(source_line, "price_female_family", None))
    else:
        base = discounted
    return discounted, base


def _get_contract_custom_prices(source_line, key: str) -> tuple[int, int]:
    extra = getattr(source_line, "extra_prices_json", None) or {}
    if key not in extra and f"{key}_udai" not in extra:
        return 0, 0
    discounted = _to_int(extra.get(key) or 0)
    base = _to_int(extra.get(f"{key}_udai") or extra.get(key) or 0)
    return discounted, base


def _build_contract_package_totals(profile, pkg_lines: list[dict], columns: list[dict], quotation_line_map: dict, catalog_price_map: dict) -> dict:
    totals_by_col = OrderedDict()

    for col in columns:
        key = col["key"]
        discounted_per_person = 0
        base_per_person = 0

        for line_data in pkg_lines:
            source_line = quotation_line_map.get(line_data.get("source_quotation_line_id"))
            if key in STANDARD_COL_KEYS:
                discounted, base = _get_contract_standard_prices(line_data, source_line, key, catalog_price_map)
            else:
                discounted, base = _get_contract_custom_prices(source_line, key)

            discounted_per_person += discounted
            base_per_person += base

        subtotal = discounted_per_person * _to_int(col.get("count") or 0)

        totals_by_col[key] = {
            "key": key,
            "label": col["label"],
            "count": _to_int(col.get("count") or 0),
            "per_person": discounted_per_person,
            "base_per_person": base_per_person,
            "per_person_display": fmt_vnd(discounted_per_person) if discounted_per_person else "",
            "base_per_person_display": fmt_vnd(base_per_person) if base_per_person else "",
            "subtotal": subtotal,
            "subtotal_display": fmt_vnd(subtotal) if subtotal else "",
        }

    grand_total = sum(v["subtotal"] for v in totals_by_col.values())

    return {
        "by_col": totals_by_col,
        "grand_total_raw": grand_total,
        "grand_total_display": fmt_vnd(grand_total) if grand_total else "",
        # compat cho code cũ
        "base_total_male": totals_by_col.get("male", {}).get("base_per_person", 0),
        "base_total_female_single": totals_by_col.get("female_single", {}).get("base_per_person", 0),
        "base_total_female_family": totals_by_col.get("female_family", {}).get("base_per_person", 0),
        "discounted_unit_male": totals_by_col.get("male", {}).get("per_person", 0),
        "discounted_unit_female_single": totals_by_col.get("female_single", {}).get("per_person", 0),
        "discounted_unit_female_family": totals_by_col.get("female_family", {}).get("per_person", 0),
        "base_total_male_display": totals_by_col.get("male", {}).get("base_per_person_display", ""),
        "base_total_female_single_display": totals_by_col.get("female_single", {}).get("base_per_person_display", ""),
        "base_total_female_family_display": totals_by_col.get("female_family", {}).get("base_per_person_display", ""),
        "discounted_unit_male_display": totals_by_col.get("male", {}).get("per_person_display", ""),
        "discounted_unit_female_single_display": totals_by_col.get("female_single", {}).get("per_person_display", ""),
        "discounted_unit_female_family_display": totals_by_col.get("female_family", {}).get("per_person_display", ""),
    }


def _get_contract_package_snapshot(profile) -> list[dict]:
    raw = getattr(profile, "package_snapshot_json", None) or []
    return raw if isinstance(raw, list) else []


def _normalize_contract_snapshot_columns(columns_raw: list | None) -> list[dict]:
    columns = []
    for raw in (columns_raw or []):
        if not isinstance(raw, dict):
            continue
        key = str(raw.get("key") or "").strip()
        if not key:
            continue
        columns.append({
            "key": key,
            "label": (raw.get("label") or key).strip(),
            "count": _to_int(raw.get("count") or 0),
            "discount_pct": float(raw.get("discount_pct") or 0),
        })
    return columns


def _normalize_contract_snapshot_line(idx: int, raw: dict) -> dict:
    line_data = {
        "id": raw.get("id") or idx,
        "stt": idx,
        "source_quotation_line_id": raw.get("source_quotation_line_id"),
        "catalog_id": raw.get("catalog_id"),
        "item_name": raw.get("item_name") or "",
        "description": raw.get("description") or "",
        "group_name": raw.get("group_name") or "Khác",
        "subgroup_name": raw.get("subgroup_name") or "",
        "group_name_en": raw.get("group_name_en") or "",
        "price_male": _to_int(raw.get("price_male")),
        "price_female_single": _to_int(raw.get("price_female_single")),
        "price_female_family": _to_int(raw.get("price_female_family")),
        "udai_price_male": _to_int(raw.get("udai_price_male")),
        "udai_price_fs": _to_int(raw.get("udai_price_fs")),
        "udai_price_ff": _to_int(raw.get("udai_price_ff")),
        "list_price": _to_int(raw.get("list_price")),
        "for_male": bool(raw.get("for_male", raw.get("checked_male", False))),
        "for_female_single": bool(raw.get("for_female_single", raw.get("checked_female_single", False))),
        "for_female_family": bool(raw.get("for_female_family", raw.get("checked_female_family", False))),
        "checked_male": bool(raw.get("checked_male", raw.get("for_male", False))),
        "checked_female_single": bool(raw.get("checked_female_single", raw.get("for_female_single", False))),
        "checked_female_family": bool(raw.get("checked_female_family", raw.get("for_female_family", False))),
        "discount_male_pct": float(raw.get("discount_male_pct") or 0),
        "discount_fs_pct": float(raw.get("discount_fs_pct") or 0),
        "discount_ff_pct": float(raw.get("discount_ff_pct") or 0),
        "price_type": raw.get("price_type") or "standard",
        "note": raw.get("note") or "",
        "display_order": _to_int(raw.get("display_order") or idx),
        "extra_prices_json": raw.get("extra_prices_json") or {},
    }
    line_data["display_unit_price"] = _price_label_for_line(line_data)
    line_data["male_mark"] = _check_label(
        line_data["for_male"], line_data["price_type"], line_data["note"],
        discount_pct=line_data["discount_male_pct"],
    )
    line_data["female_single_mark"] = _check_label(
        line_data["for_female_single"], line_data["price_type"], line_data["note"],
        discount_pct=line_data["discount_fs_pct"],
    )
    line_data["female_family_mark"] = _check_label(
        line_data["for_female_family"], line_data["price_type"], line_data["note"],
        discount_pct=line_data["discount_ff_pct"],
    )
    return line_data


def _get_contract_snapshot_custom_cell_mark(line_data: dict, key: str) -> str:
    extra = line_data.get("extra_prices_json") or {}
    if key not in extra and f"{key}_udai" not in extra:
        return "–"
    return _check_label(True, line_data.get("price_type") or "standard", line_data.get("note") or "")


def _build_contract_snapshot_line_column_cells(line_data: dict, columns: list[dict]) -> list[dict]:
    cells = []
    for col in columns:
        key = col["key"]
        if key == "male":
            mark = line_data.get("male_mark") or "–"
        elif key == "female_single":
            mark = line_data.get("female_single_mark") or "–"
        elif key == "female_family":
            mark = line_data.get("female_family_mark") or "–"
        else:
            mark = _get_contract_snapshot_custom_cell_mark(line_data, key)

        cells.append({
            "key": key,
            "label": col["label"],
            "mark": mark,
        })
    return cells


def _get_contract_snapshot_standard_prices(line_data: dict, key: str) -> tuple[int, int]:
    # list_price là giá niêm yết gốc từ catalog — dùng làm base khi tính "GIÁ NIÊM YẾT"
    list_price = _to_int(line_data.get("list_price"))

    if key == "male":
        enabled = bool(line_data.get("for_male"))
        discounted = _to_int(line_data.get("price_male")) if enabled else 0
        base = (list_price or _to_int(line_data.get("udai_price_male") or line_data.get("price_male"))) if enabled else 0
        return discounted, base

    if key == "female_single":
        enabled = bool(line_data.get("for_female_single"))
        discounted = _to_int(line_data.get("price_female_single")) if enabled else 0
        base = (list_price or _to_int(line_data.get("udai_price_fs") or line_data.get("price_female_single"))) if enabled else 0
        return discounted, base

    enabled = bool(line_data.get("for_female_family"))
    discounted = _to_int(line_data.get("price_female_family")) if enabled else 0
    base = (list_price or _to_int(line_data.get("udai_price_ff") or line_data.get("price_female_family"))) if enabled else 0
    return discounted, base


def _get_contract_snapshot_custom_prices(line_data: dict, key: str) -> tuple[int, int]:
    extra = line_data.get("extra_prices_json") or {}
    if key not in extra and f"{key}_udai" not in extra:
        return 0, 0
    discounted = _to_int(extra.get(key) or 0)
    base = _to_int(extra.get(f"{key}_udai") or extra.get(key) or 0)
    return discounted, base


def _build_contract_package_totals_from_snapshot(pkg_lines: list[dict], columns: list[dict]) -> dict:
    totals_by_col = OrderedDict()

    for col in columns:
        key = col["key"]
        discounted_per_person = 0
        base_per_person = 0

        for line_data in pkg_lines:
            if key in STANDARD_COL_KEYS:
                discounted, base = _get_contract_snapshot_standard_prices(line_data, key)
            else:
                discounted, base = _get_contract_snapshot_custom_prices(line_data, key)

            discounted_per_person += discounted
            base_per_person += base

        subtotal = discounted_per_person * _to_int(col.get("count") or 0)

        totals_by_col[key] = {
            "key": key,
            "label": col["label"],
            "count": _to_int(col.get("count") or 0),
            "per_person": discounted_per_person,
            "base_per_person": base_per_person,
            "per_person_display": fmt_vnd(discounted_per_person) if discounted_per_person else "",
            "base_per_person_display": fmt_vnd(base_per_person) if base_per_person else "",
            "subtotal": subtotal,
            "subtotal_display": fmt_vnd(subtotal) if subtotal else "",
        }

    grand_total = sum(v["subtotal"] for v in totals_by_col.values())

    return {
        "by_col": totals_by_col,
        "grand_total_raw": grand_total,
        "grand_total_display": fmt_vnd(grand_total) if grand_total else "",
        "base_total_male": totals_by_col.get("male", {}).get("base_per_person", 0),
        "base_total_female_single": totals_by_col.get("female_single", {}).get("base_per_person", 0),
        "base_total_female_family": totals_by_col.get("female_family", {}).get("base_per_person", 0),
        "discounted_unit_male": totals_by_col.get("male", {}).get("per_person", 0),
        "discounted_unit_female_single": totals_by_col.get("female_single", {}).get("per_person", 0),
        "discounted_unit_female_family": totals_by_col.get("female_family", {}).get("per_person", 0),
        "base_total_male_display": totals_by_col.get("male", {}).get("base_per_person_display", ""),
        "base_total_female_single_display": totals_by_col.get("female_single", {}).get("base_per_person_display", ""),
        "base_total_female_family_display": totals_by_col.get("female_family", {}).get("base_per_person_display", ""),
        "discounted_unit_male_display": totals_by_col.get("male", {}).get("per_person_display", ""),
        "discounted_unit_female_single_display": totals_by_col.get("female_single", {}).get("per_person_display", ""),
        "discounted_unit_female_family_display": totals_by_col.get("female_family", {}).get("per_person_display", ""),
    }


def _aggregate_contract_price_summary_from_packages(packages_payload: list[dict]) -> dict:
    base_total_male = sum(_to_int(pkg["totals"].get("base_total_male")) for pkg in packages_payload)
    base_total_fs = sum(_to_int(pkg["totals"].get("base_total_female_single")) for pkg in packages_payload)
    base_total_ff = sum(_to_int(pkg["totals"].get("base_total_female_family")) for pkg in packages_payload)

    discounted_unit_male = sum(_to_int(pkg["totals"].get("discounted_unit_male")) for pkg in packages_payload)
    discounted_unit_fs = sum(_to_int(pkg["totals"].get("discounted_unit_female_single")) for pkg in packages_payload)
    discounted_unit_ff = sum(_to_int(pkg["totals"].get("discounted_unit_female_family")) for pkg in packages_payload)

    grand_total = sum(_to_int(pkg["totals"].get("grand_total_raw")) for pkg in packages_payload)

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


def _build_contract_price_summary(profile, lines: list[dict]) -> dict:
    base_total_male = 0
    base_total_fs = 0
    base_total_ff = 0
    discounted_unit_male = 0
    discounted_unit_fs = 0
    discounted_unit_ff = 0

    male_count = _to_int(profile.male_count)
    female_single_count = _to_int(profile.female_single_count)
    female_family_count = _to_int(profile.female_family_count)

    for line in lines:
        if line.get("for_male"):
            discounted_unit_male += _to_int(line.get("price_male"))
            base_total_male += _to_int(line.get("udai_price_male") or line.get("price_male"))

        if line.get("for_female_single"):
            discounted_unit_fs += _to_int(line.get("price_female_single"))
            base_total_fs += _to_int(line.get("udai_price_fs") or line.get("price_female_single"))

        if line.get("for_female_family"):
            discounted_unit_ff += _to_int(line.get("price_female_family"))
            base_total_ff += _to_int(line.get("udai_price_ff") or line.get("price_female_family"))

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


def _build_contract_packages_payload(profile) -> tuple[list[dict], bool]:
    snapshot_packages = _get_contract_package_snapshot(profile)
    if not snapshot_packages:
        return [], False

    packages_payload = []

    for pkg in snapshot_packages:
        columns = _normalize_contract_snapshot_columns(pkg.get("columns") or [])

        raw_pkg_lines = list(pkg.get("lines") or [])
        raw_pkg_lines.sort(
            key=lambda x: (
                _to_int((x or {}).get("display_order") or 0),
                _to_int((x or {}).get("id") or 0),
            )
        )

        pkg_lines = [
            _normalize_contract_snapshot_line(idx, raw_line)
            for idx, raw_line in enumerate(raw_pkg_lines, start=1)
        ]
        if not pkg_lines:
            continue

        for idx, item in enumerate(pkg_lines, start=1):
            item["stt"] = idx
            item["column_cells"] = _build_contract_snapshot_line_column_cells(item, columns)

        grouped, display_rows = _build_display_rows(pkg_lines)
        totals = _build_contract_package_totals_from_snapshot(pkg_lines, columns)

        participant_total = sum(_to_int(col.get("count") or 0) for col in columns)

        packages_payload.append({
            "id": pkg.get("id") or f"pkg_{len(packages_payload) + 1}",
            "name": pkg.get("name") or "Gói khám",
            "display_order": _to_int(pkg.get("display_order") or len(packages_payload)),
            "columns": columns,
            "lines": pkg_lines,
            "grouped": grouped,
            "display_rows": display_rows,
            "totals": totals,
            "participant_total": participant_total,
        })

    packages_payload.sort(key=lambda x: (x.get("display_order", 0), str(x.get("id"))))
    return packages_payload, bool(packages_payload)


def _build_contract_catalog_sections(
    *,
    packages_payload: list[dict],
    lines: list[dict],
    display_rows: list[dict],
    price_summary: dict,
    profile,
) -> list[dict]:
    """
    Chuẩn hoá schema render chung cho cả:
    - HTML preview
    - HTML pdf
    - DOCX -> PDF

    Mỗi section = 1 bảng hoàn chỉnh.
    """
    if packages_payload:
        sections = []
        for pkg in packages_payload:
            totals = pkg.get("totals") or {}
            by_col = totals.get("by_col") or {}
            columns = []
            for col in (pkg.get("columns") or []):
                key = col.get("key", "")
                col_total = by_col.get(key) or {}
                columns.append({
                    "key": key,
                    "label": col.get("label", key),
                    "count": _to_int(col_total.get("count", col.get("count", 0))),
                    "base_per_person": _to_int(col_total.get("base_per_person")),
                    "base_per_person_display": col_total.get("base_per_person_display") or "",
                    "per_person": _to_int(col_total.get("per_person")),
                    "per_person_display": col_total.get("per_person_display") or "",
                    "subtotal": _to_int(col_total.get("subtotal")),
                    "subtotal_display": col_total.get("subtotal_display") or "",
                })
            sections.append({
                "id": pkg.get("id"),
                "title": pkg.get("name") or "",
                "display_order": _to_int(pkg.get("display_order")),
                "rows": pkg.get("display_rows") or [],
                "columns": columns,
                "totals": {
                    "grand_total_raw": _to_int(totals.get("grand_total")),
                    "grand_total_display": totals.get("grand_total_display") or "",
                },
            })
        return sections

    legacy_columns = [
        {
            "key": "male",
            "label": "NAM",
            "count": _to_int(getattr(profile, "male_count", 0)),
            "base_per_person": _to_int(price_summary.get("base_total_male")),
            "base_per_person_display": price_summary.get("base_total_male_display") or "",
            "per_person": _to_int(price_summary.get("discounted_unit_male")),
            "per_person_display": price_summary.get("discounted_unit_male_display") or "",
            "subtotal": _to_int(price_summary.get("discounted_unit_male")) * _to_int(getattr(profile, "male_count", 0)),
            "subtotal_display": fmt_vnd(
                _to_int(price_summary.get("discounted_unit_male")) * _to_int(getattr(profile, "male_count", 0))
            ) if _to_int(price_summary.get("discounted_unit_male")) * _to_int(getattr(profile, "male_count", 0)) else "",
        },
        {
            "key": "female_single",
            "label": "NỮ ĐỘC THÂN",
            "count": _to_int(getattr(profile, "female_single_count", 0)),
            "base_per_person": _to_int(price_summary.get("base_total_female_single")),
            "base_per_person_display": price_summary.get("base_total_female_single_display") or "",
            "per_person": _to_int(price_summary.get("discounted_unit_female_single")),
            "per_person_display": price_summary.get("discounted_unit_female_single_display") or "",
            "subtotal": _to_int(price_summary.get("discounted_unit_female_single")) * _to_int(getattr(profile, "female_single_count", 0)),
            "subtotal_display": fmt_vnd(
                _to_int(price_summary.get("discounted_unit_female_single")) * _to_int(getattr(profile, "female_single_count", 0))
            ) if _to_int(price_summary.get("discounted_unit_female_single")) * _to_int(getattr(profile, "female_single_count", 0)) else "",
        },
        {
            "key": "female_family",
            "label": "NỮ GIA ĐÌNH",
            "count": _to_int(getattr(profile, "female_family_count", 0)),
            "base_per_person": _to_int(price_summary.get("base_total_female_family")),
            "base_per_person_display": price_summary.get("base_total_female_family_display") or "",
            "per_person": _to_int(price_summary.get("discounted_unit_female_family")),
            "per_person_display": price_summary.get("discounted_unit_female_family_display") or "",
            "subtotal": _to_int(price_summary.get("discounted_unit_female_family")) * _to_int(getattr(profile, "female_family_count", 0)),
            "subtotal_display": fmt_vnd(
                _to_int(price_summary.get("discounted_unit_female_family")) * _to_int(getattr(profile, "female_family_count", 0))
            ) if _to_int(price_summary.get("discounted_unit_female_family")) * _to_int(getattr(profile, "female_family_count", 0)) else "",
        },
    ]
    return [{
        "id": "legacy_contract_catalog",
        "title": "",
        "display_order": 0,
        "rows": display_rows or [],
        "columns": legacy_columns,
        "totals": {
            "grand_total_raw": _to_int(price_summary.get("grand_total_raw")),
            "grand_total_display": price_summary.get("grand_total_display") or "",
        },
    }]


def build_contract_document_payload(contract) -> dict:
    profile = contract.corporate_profile

    blood_rows = []
    for row in contract.blood_collection_schedules.order_by("collection_date", "id"):
        blood_rows.append({
            "collection_date": row.collection_date.isoformat() if row.collection_date else "",
            "collection_date_vi": _vi_date(row.collection_date),
            "collection_date_short": _vi_date_short(row.collection_date),
            "location": row.location or "",
            "people_count": row.people_count,
            "staff_count": row.staff_count,
            "note": row.note or "",
        })

    raw_lines = list(contract.service_lines.order_by("display_order", "id"))
    catalog_price_map = _load_catalog_price_map()
    snapshot_line_map = {}
    for pkg in _get_contract_package_snapshot(profile):
        for raw_line in (pkg.get("lines") or []):
            src_id = raw_line.get("source_quotation_line_id")
            if src_id is not None and src_id not in snapshot_line_map:
                snapshot_line_map[src_id] = raw_line
    lines = []
    for idx, line in enumerate(raw_lines, start=1):
        snapshot_line = snapshot_line_map.get(getattr(line, "source_quotation_line_id", None), {})
        
        line_data = {
            "id": line.id,
            "stt": idx,
            "source_quotation_line_id": getattr(line, "source_quotation_line_id", None),
            "catalog_service_id": getattr(line, "catalog_service_id", None),
            "catalog_id": snapshot_line.get("catalog_id"),
            "item_name": line.item_name,
            "description": line.description or "",
            "group_name": line.group_name or "Khác",
            "subgroup_name": getattr(line, "subgroup_name", "") or "",
            "group_name_en": getattr(line, "group_name_en", "") or "",
            "price_male": _to_int(line.price_male),
            "price_female_single": _to_int(line.price_female_single),
            "price_female_family": _to_int(line.price_female_family),
            "udai_price_male": _to_int(snapshot_line.get("udai_price_male")),
            "udai_price_fs": _to_int(snapshot_line.get("udai_price_fs")),
            "udai_price_ff": _to_int(snapshot_line.get("udai_price_ff")),
            "list_price": _to_int(snapshot_line.get("list_price")),
            "for_male": bool(line.for_male),
            "for_female_single": bool(line.for_female_single),
            "for_female_family": bool(line.for_female_family),
            "discount_male_pct": float(getattr(line, "discount_male_pct", 0) or 0),
            "discount_fs_pct": float(getattr(line, "discount_fs_pct", 0) or 0),
            "discount_ff_pct": float(getattr(line, "discount_ff_pct", 0) or 0),
            "price_type": getattr(line, "price_type", "standard") or "standard",
            "note": line.note or "",
            "display_order": line.display_order,
            "extra_prices_json": snapshot_line.get("extra_prices_json") or {},
        }
        line_data["display_unit_price"] = _price_label_for_line(line_data)
        line_data["male_mark"] = _check_label(line_data["for_male"], line_data["price_type"], line_data["note"], discount_pct=line_data["discount_male_pct"])
        line_data["female_single_mark"] = _check_label(line_data["for_female_single"], line_data["price_type"], line_data["note"], discount_pct=line_data["discount_fs_pct"])
        line_data["female_family_mark"] = _check_label(line_data["for_female_family"], line_data["price_type"], line_data["note"], discount_pct=line_data["discount_ff_pct"])
        lines.append(line_data)

    grouped = OrderedDict()
    display_rows = []
    for line in lines:
        group_name = line["group_name"] or "Khác"
        subgroup_name = line["subgroup_name"] or ""
        if group_name not in grouped:
            grouped[group_name] = {"items": [], "subgroups": OrderedDict()}
            display_rows.append({"row_type": "group", "label": group_name})
        if subgroup_name:
            if subgroup_name not in grouped[group_name]["subgroups"]:
                grouped[group_name]["subgroups"][subgroup_name] = []
                display_rows.append({"row_type": "subgroup", "label": subgroup_name, "group_name": group_name})
            grouped[group_name]["subgroups"][subgroup_name].append(line)
        else:
            grouped[group_name]["items"].append(line)
        display_rows.append({"row_type": "item", "group_name": group_name, "subgroup_name": subgroup_name, "line": line})
    
    packages_payload, multi_package = _build_contract_packages_payload(profile)
    if packages_payload:
        price_summary = _aggregate_contract_price_summary_from_packages(packages_payload)
    else:
        price_summary = _build_contract_price_summary(profile, lines)

    catalog_sections = _build_contract_catalog_sections(
        packages_payload=packages_payload,
        lines=lines,
        display_rows=display_rows,
        price_summary=price_summary,
        profile=profile,
    )

    subtotal_male = price_summary["discounted_unit_male_display"]
    subtotal_fs = price_summary["discounted_unit_female_single_display"]
    subtotal_ff = price_summary["discounted_unit_female_family_display"]
    grand_total = price_summary["grand_total_raw"] or _to_int(profile.grand_total)

    deposit_pct = float(profile.deposit_pct or 30)
    deposit_amount = _to_int(profile.deposit_amount) or int(grand_total * deposit_pct / 100)
    settlement_days = profile.settlement_days or 10

    from datetime import date as date_cls
    issue_date = profile.contract_date or date_cls.today()
    year = issue_date.year
    contract_number = contract.contract_number or ""
    contract_number_full = contract_number if contract_number else f"<___>/HĐKD-VMD/<{year}>"

    start_date_vi = _vi_date_short(contract.start_date)
    end_date_vi = _vi_date_short(contract.end_date)
    period_text = ""
    if contract.start_date and contract.end_date:
        period_text = f"{start_date_vi} - {end_date_vi}"
    elif contract.start_date:
        period_text = f"Từ {start_date_vi}"

    reception_date_vi = _vi_date_short(contract.reception_from_date)
    blood_collection_from_at = getattr(profile, "blood_collection_from_at", None)
    blood_collection_to_at = getattr(profile, "blood_collection_to_at", None)
    blood_time_from = _vi_time(profile.blood_collection_time_from)
    blood_time_to = _vi_time(profile.blood_collection_time_to)
    blood_collection_from_text = _vi_date_short(blood_collection_from_at.date()) if blood_collection_from_at else ""
    blood_collection_to_text = _vi_date_short(blood_collection_to_at.date()) if blood_collection_to_at else ""
    blood_time_text = ""
    if blood_collection_from_at and blood_collection_to_at:
        blood_time_text = (
            f"Từ {_vi_date_short(blood_collection_from_at.date())} {blood_collection_from_at.strftime('%H:%M')} "
            f"đến {_vi_date_short(blood_collection_to_at.date())} {blood_collection_to_at.strftime('%H:%M')}"
        )
    elif blood_collection_from_at:
        blood_time_text = f"Từ {_vi_date_short(blood_collection_from_at.date())} {blood_collection_from_at.strftime('%H:%M')}"
    elif blood_time_from and blood_time_to:
        blood_time_text = f"Từ {blood_time_from} đến {blood_time_to}"
    elif blood_time_from:
        blood_time_text = f"Từ {blood_time_from}"

    deposit_deadline_vi = _vi_date_short(profile.deposit_deadline)
    deposit_pct_display = f"{deposit_pct:g}%"
    deposit_amount_words = (getattr(profile, "deposit_amount_words", None) or "").strip()

    quotation_extra_content = (profile.quotation_extra_content_snapshot or "").strip()
    
    payload = {
        "contract_number": contract_number,
        "contract_number_full": contract_number_full,
        "issue_day": str(issue_date.day),
        "issue_month": str(issue_date.month),
        "issue_year": str(issue_date.year),
        "issue_date": _vi_date_short(issue_date),
        "issue_date_vi": _vi_date(issue_date),
        "company_name": profile.company_name_snapshot or "",
        "company_address": profile.company_address_snapshot or "",
        "company_phone": profile.company_phone_snapshot or "",
        "company_tax_code": profile.company_tax_code_snapshot or "",
        "contact_person": profile.contact_person_snapshot or contract.contact_person or "",
        "representative_title": profile.representative_title_snapshot or contract.representative_title or "",
        "signer_b_name": profile.signer_b_name or "",
        "signer_b_title": profile.signer_b_title or "",
        "signer_a_name": profile.signer_a_name or "TS.BS. PHẠM THẾ VIỆT",
        "signer_a_title": profile.signer_a_title or "Tổng Giám Đốc",
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
        "male_count": profile.male_count or 0,
        "female_single_count": profile.female_single_count or 0,
        "female_family_count": profile.female_family_count or 0,
        "total_pax": (profile.male_count or 0) + (profile.female_single_count or 0) + (
                profile.female_family_count or 0),
        "base_total_male": price_summary["base_total_male"],
        "base_total_female_single": price_summary["base_total_female_single"],
        "base_total_female_family": price_summary["base_total_female_family"],
        "base_total_male_display": price_summary["base_total_male_display"],
        "base_total_female_single_display": price_summary["base_total_female_single_display"],
        "base_total_female_family_display": price_summary["base_total_female_family_display"],
        "subtotal_male": subtotal_male,
        "subtotal_female_single": subtotal_fs,
        "subtotal_female_family": subtotal_ff,
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
        "contract_note": profile.contract_note or "",
        "quotation_note": profile.quotation_note or "",
        "note": contract.note or "",
        "extra_content": quotation_extra_content,
        "lines": lines,
        "grouped": grouped,
        "display_rows": display_rows,
        "blood_rows": blood_rows,
        "packages": packages_payload,
        "multi_package": multi_package,
        "catalog_sections": catalog_sections,
    }
    return payload


def build_contract_preview_context(contract) -> dict:
    payload = build_contract_document_payload(contract)
    return {
        "contract": contract,
        "contract_payload": payload,
        "catalog_sections": payload.get("catalog_sections", []),
        "packages": payload.get("packages", []),  # compat
        "multi_package": payload.get("multi_package", False),  # compat
        "lines": payload["lines"],  # compat
        "grouped": payload["grouped"],  # compat
        "display_rows": payload["display_rows"],  # compat
        "blood_rows": payload["blood_rows"],
        "fmt_vnd": fmt_vnd,
    }
