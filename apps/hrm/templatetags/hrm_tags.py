from django import template

register = template.Library()


@register.filter(name="in_group")
def in_group(user, group_name):
    """
    Kiểm tra user có thuộc group_name hay không.
    Dùng trong template:
        {% if request.user|in_group:"HR Admin" %}
    """
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if not group_name:
        return False
    return user.groups.filter(name=group_name).exists()


@register.filter(name="get_item")
def get_item(dictionary, key):
    """
    Truy cập dict bằng biến trong template.
    Dùng: {{ my_dict|get_item:some_var }}
    """
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None
