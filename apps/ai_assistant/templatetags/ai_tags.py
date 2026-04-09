from django import template
from apps.ai_assistant.permissions import user_can_access_ai

register = template.Library()


@register.simple_tag(takes_context=True)
def can_use_ai(context):
    """
    Trả về True nếu user hiện tại có quyền dùng AI assistant.

    Dùng trong template:
        {% load ai_tags %}
        {% can_use_ai as ai_ok %}
        {% if ai_ok %}
          <a href="{% url 'ai_assistant:index' %}">Trợ lý AI</a>
        {% endif %}
    """
    request = context.get("request")
    if request is None:
        return False
    return user_can_access_ai(request.user)
