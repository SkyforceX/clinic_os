"""
apps/hrm/templatetags/hrm_tags.py
====================================
Template tags và filters dùng chung cho HRM và dashboard.
"""

from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """
    Tra cứu key trong dict.
    Usage: ds.shifts|get_item:wdi.day_key
    Giữ nguyên để không break DoctorSchedule template cũ.
    """
    if not isinstance(dictionary, dict):
        return None
    return dictionary.get(key)


@register.filter
def dict_get(d, key):
    """Alias cho get_item — dùng trong work_schedule templates."""
    if not isinstance(d, dict):
        return None
    return d.get(key)


@register.filter
def dict_get_key(d, key):
    """Direct dict key lookup. Usage: shift_display|dict_get_key:shift."""
    if not isinstance(d, dict):
        return {}
    return d.get(key, {})


@register.filter(name='split')
def split_filter(value, sep=","):
    """Split string. Usage: 'a,b,c'|split:',' """
    return str(value).split(sep)


@register.filter
def add_str(value, arg):
    """Concatenate two strings."""
    return str(value) + str(arg)


@register.filter
def shift_css(shift):
    """Trả về CSS class cho mã ca làm việc."""
    mapping = {
        'F': 'shift-f',
        'S': 'shift-s',
        'C': 'shift-c',
        'L': 'shift-l',
        'O': 'shift-o',
    }
    return mapping.get(str(shift).upper(), 'shift-empty')


@register.filter
def shift_label(shift):
    """Trả về nhãn tiếng Việt cho mã ca."""
    labels = {
        'F': 'Cả ngày',
        'S': 'Ca sáng',
        'C': 'Ca chiều',
        'L': 'Nghỉ lễ',
        'O': 'Không làm',
    }
    return labels.get(str(shift).upper(), 'Chưa đăng ký')
