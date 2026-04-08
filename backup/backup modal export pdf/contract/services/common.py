import re
from datetime import date, datetime

from django.db import transaction
from django.forms import ValidationError

from apps.contract.models import Contract, ContractNumberSequence


def parse_date(value, required=True, field_label="ngày"):
    if not value:
        if required:
            raise ValidationError(f"Vui lòng nhập {field_label}.")
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    value = str(value).strip()
    if not value:
        if required:
            raise ValidationError(f"Vui lòng nhập {field_label}.")
        return None

    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue

    raise ValidationError(
        f"{field_label.capitalize()} không đúng định dạng. Định dạng hợp lệ: dd/mm/yyyy hoặc yyyy-mm-dd."
    )


def parse_datetime_local(value, required=False, field_label="ngày giờ"):
    if not value:
        if required:
            raise ValidationError(f"Vui lòng nhập {field_label}.")
        return None

    if isinstance(value, datetime):
        return value

    value = str(value).strip()
    if not value:
        if required:
            raise ValidationError(f"Vui lòng nhập {field_label}.")
        return None

    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue

    raise ValidationError(f"{field_label.capitalize()} không đúng định dạng.")


def parse_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_money(value, default=0):
    if value in (None, ""):
        return default
    cleaned = re.sub(r"[^\d\-]", "", str(value))
    if not cleaned:
        return default
    try:
        return int(cleaned)
    except (TypeError, ValueError):
        return default


@transaction.atomic
def reserve_next_contract_number(year=None):
    """
    Sinh số hợp đồng duy nhất theo format:
    <01>/HĐKD-VMD/<2026>

    Dùng bảng ContractNumberSequence để tránh trùng khi nhiều request đồng thời.
    """
    year = int(year or datetime.now().year)

    seq, _ = ContractNumberSequence.objects.select_for_update().get_or_create(
        year=year,
        defaults={"last_value": 0},
    )
    seq.last_value += 1
    seq.save(update_fields=["last_value", "updated_at"])

    return f"{seq.last_value:02d}/HĐKD-VMD/{year}"


def get_next_contract_number():
    """
    Alias giữ tương thích cho code cũ.
    """
    return reserve_next_contract_number()


_VN_DIGITS = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]


def _read_three_digits(number, full=False):
    number = int(number)
    hundred = number // 100
    ten = (number % 100) // 10
    unit = number % 10
    parts = []

    if full or hundred > 0:
        parts.append(f"{_VN_DIGITS[hundred]} trăm")

    if ten > 1:
        parts.append(f"{_VN_DIGITS[ten]} mươi")
        if unit == 1:
            parts.append("mốt")
        elif unit == 4:
            parts.append("tư")
        elif unit == 5:
            parts.append("lăm")
        elif unit > 0:
            parts.append(_VN_DIGITS[unit])
    elif ten == 1:
        parts.append("mười")
        if unit == 5:
            parts.append("lăm")
        elif unit > 0:
            parts.append(_VN_DIGITS[unit])
    elif ten == 0:
        if unit > 0:
            if hundred > 0 or full:
                parts.append("lẻ")
            parts.append(_VN_DIGITS[unit])

    return " ".join(parts).strip()


def money_to_vietnamese_words(amount):
    try:
        amount = int(amount or 0)
    except (TypeError, ValueError):
        amount = 0

    if amount <= 0:
        return "Không đồng"

    units = ["", "nghìn", "triệu", "tỷ", "nghìn tỷ", "triệu tỷ"]
    groups = []
    while amount > 0:
        groups.append(amount % 1000)
        amount //= 1000

    words = []
    for idx in range(len(groups) - 1, -1, -1):
        group_value = groups[idx]
        if group_value == 0:
            continue
        full = idx < len(groups) - 1 and group_value < 100
        chunk = _read_three_digits(group_value, full=full)
        unit = units[idx] if idx < len(units) else ""
        if chunk:
            words.append(f"{chunk} {unit}".strip())

    sentence = " ".join(words).strip()
    sentence = re.sub(r"\s+", " ", sentence)
    return sentence[:1].upper() + sentence[1:] + " đồng"