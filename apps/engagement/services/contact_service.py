"""
engagement/services/contact_service.py
==================================
Upload danh sách liên hệ từ Excel, masking SĐT, phân công agent.
"""
from __future__ import annotations

import re
from datetime import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

User = get_user_model()

# Cột Excel mặc định (có thể override bằng field_mapping)
DEFAULT_FIELD_MAP = {
    "Họ tên":       "full_name",
    "Tên":          "full_name",
    "Họ và tên":    "full_name",
    "Số điện thoại":"phone_raw",
    "SĐT":          "phone_raw",
    "Phone":        "phone_raw",
    "Email":        "email",
    "Công ty":      "company_name",
    "Tên công ty":  "company_name",
    "Chức vụ":      "position",
    "Địa chỉ":      "address",
}


def _normalize_phone(raw: str) -> str:
    """Chuẩn hóa số điện thoại Việt Nam."""
    digits = re.sub(r"[^\d+]", "", str(raw or ""))
    if digits.startswith("+84"):
        digits = "0" + digits[3:]
    if digits.startswith("84") and len(digits) >= 10:
        digits = "0" + digits[2:]
    return digits


def _read_excel_rows(file_obj) -> tuple[list[str], list[list]]:
    """Đọc file Excel, trả về (headers, rows)."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(file_obj, data_only=True, read_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return [], []
        headers = [str(h or "").strip() for h in rows[0]]
        data    = [list(r) for r in rows[1:] if any(c for c in r)]
        wb.close()
        return headers, data
    except Exception as exc:
        raise ValidationError(f"Không đọc được file Excel: {exc}")


@transaction.atomic
def import_contacts_from_excel(
    *,
    actor,
    contact_list,
    file_obj,
    field_mapping: dict[str, str] | None = None,
    overwrite: bool = False,
) -> dict:
    """
    Đọc Excel và tạo Contact records.
    field_mapping: {tên_cột_excel: field_name} override DEFAULT_FIELD_MAP.
    """
    from apps.engagement.models import Contact

    mapping = {**DEFAULT_FIELD_MAP, **(field_mapping or {})}
    headers, rows = _read_excel_rows(file_obj)

    # Build column index map
    col_idx: dict[str, int] = {}
    for idx, h in enumerate(headers):
        if h in mapping:
            col_idx[mapping[h]] = idx

    if "phone_raw" not in col_idx:
        raise ValidationError("Không tìm thấy cột Số điện thoại trong file Excel.")

    if overwrite:
        contact_list.contacts.all().delete()

    contacts_to_create = []
    errors = []
    existing_phones = set(
        contact_list.contacts.values_list("phone_raw", flat=True)
    )

    for row_num, row in enumerate(rows, start=2):
        def get(field):
            idx = col_idx.get(field)
            if idx is None or idx >= len(row):
                return ""
            return str(row[idx] or "").strip()

        phone = _normalize_phone(get("phone_raw"))
        if not phone:
            errors.append(f"Hàng {row_num}: Thiếu số điện thoại.")
            continue

        if phone in existing_phones:
            errors.append(f"Hàng {row_num}: SĐT {phone[:3]}****{phone[-3:]} đã tồn tại, bỏ qua.")
            continue

        # Extra data = tất cả cột không map được
        extra = {}
        for idx, h in enumerate(headers):
            if h and mapping.get(h) not in ("phone_raw","full_name","email","company_name","position","address"):
                val = row[idx] if idx < len(row) else None
                if val is not None:
                    extra[h] = str(val).strip()

        contacts_to_create.append(Contact(
            contact_list  = contact_list,
            full_name     = get("full_name") or f"KH {row_num}",
            phone_raw     = phone,
            email         = get("email"),
            company_name  = get("company_name"),
            position      = get("position"),
            address       = get("address"),
            extra_data    = extra,
            row_number    = row_num,
        ))
        existing_phones.add(phone)

    Contact.objects.bulk_create(contacts_to_create, batch_size=500)

    return {
        "created": len(contacts_to_create),
        "errors":  errors,
        "total_rows": len(rows),
    }


@transaction.atomic
def assign_contacts_to_agent(
    *,
    actor,
    contact_ids: list[int],
    agent_id: int | None,
) -> int:
    """Phân công danh sách contacts cho agent."""
    from apps.engagement.models import Contact
    qs = Contact.objects.filter(id__in=contact_ids)
    count = qs.count()
    qs.update(
        assigned_to_id=agent_id,
        status=Contact.Status.ASSIGNED if agent_id else Contact.Status.NEW,
    )
    return count


@transaction.atomic
def log_call(
    *,
    agent,
    contact_id: int,
    outcome: str,
    channel: str = "PHONE",
    duration_s: int = 0,
    note: str = "",
    follow_up_at=None,
) -> "CallLog":
    """Ghi nhận một lần liên hệ và cập nhật trạng thái contact."""
    from apps.engagement.models import CallLog, Contact

    contact = Contact.objects.select_for_update().get(pk=contact_id)

    log = CallLog.objects.create(
        contact=contact,
        agent=agent,
        channel=channel,
        outcome=outcome,
        duration_s=duration_s,
        note=note,
        follow_up_at=follow_up_at,
    )

    # Map outcome → contact status
    STATUS_MAP = {
        "REACHED":        Contact.Status.REACHED,
        "INTERESTED":     Contact.Status.INTERESTED,
        "NOT_INTERESTED": Contact.Status.NOT_INTERESTED,
        "CONVERTED":      Contact.Status.CONVERTED,
        "DO_NOT_CALL":    Contact.Status.DO_NOT_CALL,
        "CALLBACK":       Contact.Status.FOLLOW_UP,
        "NO_ANSWER":      contact.status,  # giữ nguyên
        "BUSY":           contact.status,
        "WRONG_NUMBER":   Contact.Status.NOT_REACHED,
    }
    new_status = STATUS_MAP.get(outcome, contact.status)
    contact.status       = new_status
    contact.last_call_at = timezone.now()
    contact.call_count   = contact.call_count + 1
    if follow_up_at:
        contact.follow_up_at = follow_up_at
    contact.save(update_fields=["status","last_call_at","call_count","follow_up_at"])

    return log
