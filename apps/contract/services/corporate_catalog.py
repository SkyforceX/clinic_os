# apps/contract/services/corporate_catalog.py
import json
from pathlib import Path


CATALOG_PATH = Path(__file__).resolve().parent.parent / "static" / "contract" / "data" / "catalog.json"


def load_corporate_service_catalog():
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)
    # catalog.json có dạng {"catalog": [...]} hoặc [...]
    if isinstance(raw, dict):
        return {"items": raw.get("catalog") or raw.get("items") or []}
    return {"items": raw}


def get_catalog_items():
    return load_corporate_service_catalog().get("items", [])


def get_catalog_item_map():
    items = get_catalog_items()
    # catalog.json dùng "id" làm key, corporate dùng "code"
    # map bằng str(id) để tương thích với cả hai
    result = {}
    for item in items:
        key = str(item.get("code") or item.get("id") or "")
        if key:
            # Chuẩn hóa field names về format mà corporate_contracts.py mong đợi
            result[key] = {
                "code": key,
                "item_name": item.get("name") or item.get("item_name") or "",
                "description": item.get("description") or "",
                "group_name": item.get("group") or item.get("group_name") or "",
                "price_male": int(item.get("price_male") or 0),
                "price_female_single": int(item.get("price_female_single") or 0),
                "price_female_family": int(item.get("price_female_family") or 0),
            }
    return result