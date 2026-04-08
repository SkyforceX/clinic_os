from django import template
from apps.meeting.domain.enums import MEETING_STEP_LABELS

register = template.Library()


@register.simple_tag
def meeting_steps():
    return list(MEETING_STEP_LABELS.items())


@register.filter
def get_step_label(step_num):
    return MEETING_STEP_LABELS.get(step_num, "")
