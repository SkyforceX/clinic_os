from django import template

from apps.core.templatetags.core_tags import vnd as shared_vnd


register = template.Library()


@register.filter(name="vnd")
def vnd(value):
    return shared_vnd(value)