def _safe_int(value):
    try:
        return int(value or 0)
    except Exception:
        return 0


def build_contract_package_snapshot_from_quotation(quotation, *, participant_counts: dict) -> list[dict]:
    """
    Snapshot package/columns/lines từ báo giá sang hợp đồng.
    Sau khi snapshot xong, preview/doc contract không cần đọc lại quotation nữa.
    """
    packages = list(quotation.packages.prefetch_related("lines").order_by("display_order", "id"))
    if not packages:
        return []

    male_count = _safe_int(participant_counts.get("male_count"))
    female_single_count = _safe_int(participant_counts.get("female_single_count"))
    female_family_count = _safe_int(participant_counts.get("female_family_count"))

    payload = []

    for pkg in packages:
        columns = []
        for raw in (pkg.columns_json or []):
            if not isinstance(raw, dict):
                continue
            key = str(raw.get("key") or "").strip()
            if not key:
                continue
            columns.append({
                "key": key,
                "label": (raw.get("label") or key).strip(),
                "count": _safe_int(raw.get("count") or 0),
                "discount_pct": float(raw.get("discount_pct") or 0),
            })

        lines_payload = []
        for idx, line in enumerate(pkg.lines.order_by("display_order", "id"), start=1):
            price_male = _safe_int(getattr(line, "price_male", 0))
            price_fs = _safe_int(getattr(line, "price_female_single", 0))
            price_ff = _safe_int(getattr(line, "price_female_family", 0))

            checked_male = bool(getattr(line, "checked_male", False))
            checked_fs = bool(getattr(line, "checked_female_single", False))
            checked_ff = bool(getattr(line, "checked_female_family", False))

            lines_payload.append({
                "id": line.id,
                "stt": idx,
                "source_quotation_line_id": line.id,
                "catalog_id": getattr(line, "catalog_id", None),
                "item_name": line.item_name,
                "description": line.description or "",
                "group_name": line.group_name or "Khác",
                "subgroup_name": line.subgroup_name or "",
                "group_name_en": "",
                "price_male": price_male,
                "price_female_single": price_fs,
                "price_female_family": price_ff,
                "udai_price_male": _safe_int(getattr(line, "udai_price_male", 0)),
                "udai_price_fs": _safe_int(getattr(line, "udai_price_fs", 0)),
                "udai_price_ff": _safe_int(getattr(line, "udai_price_ff", 0)),
                "list_price": _safe_int(getattr(line, "list_price", 0)),
                "for_male": male_count > 0 and checked_male and price_male > 0,
                "for_female_single": female_single_count > 0 and checked_fs and price_fs > 0,
                "for_female_family": female_family_count > 0 and checked_ff and price_ff > 0,
                "checked_male": checked_male,
                "checked_female_single": checked_fs,
                "checked_female_family": checked_ff,
                "discount_male_pct": float(getattr(line, "discount_male_pct", 0) or 0),
                "discount_fs_pct": float(getattr(line, "discount_fs_pct", 0) or 0),
                "discount_ff_pct": float(getattr(line, "discount_ff_pct", 0) or 0),
                "price_type": getattr(line, "price_type", "standard") or "standard",
                "note": getattr(line, "note", "") or "",
                "display_order": getattr(line, "display_order", idx),
                "extra_prices_json": getattr(line, "extra_prices_json", None) or {},
            })

        payload.append({
            "id": pkg.id,
            "name": pkg.name,
            "display_order": pkg.display_order,
            "columns": columns,
            "lines": lines_payload,
        })

    return payload