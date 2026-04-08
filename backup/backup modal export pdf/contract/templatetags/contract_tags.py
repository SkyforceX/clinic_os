from django import template

register = template.Library()


@register.filter(name="vnd")
def vnd(value):
    """
    Format số tiền theo chuẩn Việt Nam: dấu chấm phân cách hàng nghìn.
    Ví dụ: 1207500 → 1.207.500
    Xử lý cả string (từ ContractServiceDetail.price_male) và số.
    """
    if value in (None, "", "0", 0):
        return "–"
    try:
        # Strip commas/spaces before parsing (handles "1,200,000" or "120.000")
        cleaned = str(value).replace(",", "").replace(".", "").strip()
        num = int(float(cleaned))
        if num == 0:
            return "–"
        return f"{num:,}".replace(",", ".")
    except (TypeError, ValueError):
        # Return as-is for "Miễn phí", "TẶNG", etc.
        return str(value) if value else "–"