from django import template

register = template.Library()

@register.filter
def to(value, arg):
    """
    Trả về range(value, arg), dùng trong vòng lặp.
    Ví dụ: 1|to:5 => range(1, 5)
    """
    return range(value, arg)


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


@register.filter
def get_shift_data(daily_schedule_data, shift_key):
    if daily_schedule_data:
        return daily_schedule_data.get(shift_key)
    return None

@register.filter
def user_in_group(user, group_name):
    return user.groups.filter(name=group_name).exists()