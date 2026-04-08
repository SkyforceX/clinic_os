from django.urls import path
from apps.targets.web.views.dashboard_views import (
    ajax_bulk_monthly,
    target_delete,
    target_detail,
    target_form,
    team_dashboard,
)

app_name = "targets"

urlpatterns = [
    path("",                        team_dashboard,    name="dashboard"),
    path("new/",                    target_form,       name="create"),
    path("<int:target_id>/edit/",   target_form,       name="edit"),
    path("<int:target_id>/delete/", target_delete,     name="delete"),
    path("<int:target_id>/",        target_detail,     name="detail"),
    path("api/bulk-monthly/",       ajax_bulk_monthly, name="ajax_bulk_monthly"),
]
