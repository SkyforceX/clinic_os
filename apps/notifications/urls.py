from django.urls import path

from apps.notifications import views

app_name = "notifications"

urlpatterns = [
    path("unread-count/", views.unread_count, name="unread_count"),
]
