import json
from pathlib import Path


CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "corporate_service_catalog.json"


def load_corporate_service_catalog():
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        payload = json.load(f)
    return payload


def get_catalog_items():
    payload = load_corporate_service_catalog()
    return payload.get("items", [])


def get_catalog_item_map():
    return {item["code"]: item for item in get_catalog_items()}