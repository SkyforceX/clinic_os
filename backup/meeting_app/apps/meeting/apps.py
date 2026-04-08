from django.apps import AppConfig


class MeetingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.meeting"
    label = "meeting"
    verbose_name = "Meeting"
