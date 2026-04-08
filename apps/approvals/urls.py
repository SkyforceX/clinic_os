from django.urls import path

from apps.approvals.web.views import approval_views

app_name = "approvals"

urlpatterns = [
    path("",                       approval_views.inbox,       name="inbox"),
    path("my/",                    approval_views.my_requests, name="my_requests"),
    path("<int:pk>/",              approval_views.detail,      name="detail"),
    path("<int:pk>/approve/",      approval_views.approve,     name="approve"),
    path("<int:pk>/reject/",       approval_views.reject,      name="reject"),
    path("<int:pk>/recall/",       approval_views.recall,      name="recall"),
]
