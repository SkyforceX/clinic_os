from django import template

from apps.core.services.sidebar import build_sidebar_for_request

register = template.Library()


@register.simple_tag(takes_context=True)
def get_sidebar_sections(context):
    request = context.get("request")
    if not request or not getattr(request, "user", None) or not request.user.is_authenticated:
        return []
    return build_sidebar_for_request(request)