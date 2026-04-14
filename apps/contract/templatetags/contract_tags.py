from django import template

from apps.core.templatetags.core_tags import vnd as shared_vnd


register = template.Library()


@register.filter(name="vnd")
def vnd(value):
    return shared_vnd(value)


@register.filter(name="dict_get")
def dict_get(d, key):
    """
    Lấy giá trị từ dict bằng key động trong template.

    Dùng trong multi-package khi key là biến:
        {% with ct=by_col|dict_get:col.key %}

    Trả về {} (empty dict) nếu không tìm thấy để tránh AttributeError khi
    template tiếp tục truy cập .base_per_person_display, .per_person_display, v.v.
    """
    if not isinstance(d, dict):
        return {}
    return d.get(key, {})


@register.filter(name="col_width_pct")
def col_width_pct(num_cols):
    """
    Tính % width cho mỗi cột đối tượng trong bảng multi-package.
    STT=5%, SVC=44%, PRICE=13% → còn lại 38% chia đều cho num_cols.
    """
    try:
        n = int(num_cols)
        if n <= 0:
            return "12"
        remaining = 38
        return str(round(remaining / n, 1))
    except (ValueError, TypeError):
        return "12"
