from decimal import Decimal, InvalidOperation

from django import template


register = template.Library()


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


def _coerce_number(value):
    """
    Chuẩn hóa value về Decimal/int nếu có thể.

    Hỗ trợ:
    - int, float, Decimal
    - string dạng: "1200000", "1,200,000", "1.200.000", " 1200000 "
    - giữ nguyên None / rỗng / text không phải số
    """
    if value in (None, "", "0", 0):
        return None

    if isinstance(value, Decimal):
        return value

    if isinstance(value, (int, float)):
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return None

    text = str(value).strip()
    if not text:
        return None

    # Trường hợp text đặc biệt không phải số
    lowered = text.lower()
    if lowered in {"miễn phí", "tặng", "free", "gift", "-"}:
        return None

    # Chuẩn hóa chuỗi số
    # Dùng logic cũ của contract: bỏ cả dấu "," và "."
    cleaned = text.replace(",", "").replace(".", "").replace(" ", "")
    if not cleaned:
        return None

    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError, TypeError):
        return None


@register.filter(name="vnd")
def vnd(value):
    """
    Format số theo chuẩn VN:
    1207500 -> 1.207.500

    Nếu value là 0/rỗng -> "–"
    Nếu value là text không parse được số -> trả về nguyên text
    """
    if value in (None, "", "0", 0):
        return "–"

    num = _coerce_number(value)
    if num is None:
        return str(value) if value not in (None, "") else "–"

    try:
        integer_value = int(num)
    except (ValueError, TypeError):
        return str(value) if value not in (None, "") else "–"

    if integer_value == 0:
        return "–"

    return f"{integer_value:,}".replace(",", ".")


@register.filter(name="money_tag")
def money_tag(value):
    """
    Render text tiền để dùng trong badge/tag:
    1200000 -> 1.200.000 ₫
    """
    formatted = vnd(value)
    if formatted == "–":
        return formatted
    return f"{formatted} ₫"


@register.filter(name="money_or_text")
def money_or_text(value):
    """
    Nếu là số -> format tiền VN.
    Nếu là text như 'Miễn phí', 'TẶNG' -> trả nguyên text.
    """
    if value in (None, "", 0, "0"):
        return "–"

    num = _coerce_number(value)
    if num is None:
        return str(value).strip() or "–"

    return f"{int(num):,}".replace(",", ".")


@register.simple_tag
def money_badge_class(value):
    """
    Trả về class gợi ý cho badge tiền:
    - 0 / miễn phí -> badge-success
    - text gift/tặng -> badge-warning
    - mặc định -> badge-primary
    """
    if value in (None, "", 0, "0"):
        return "bg-light text-muted border"

    text = str(value).strip().lower()
    if text in {"miễn phí", "free"}:
        return "bg-success"
    if text in {"tặng", "gift"}:
        return "bg-warning text-dark"

    num = _coerce_number(value)
    if num is not None and int(num) == 0:
        return "bg-success"

    return "bg-primary"