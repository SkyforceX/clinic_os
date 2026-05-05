from django.urls import path

from . import views

app_name = "ai_assistant"

urlpatterns = [
    path("", views.ManagerAssistantIndexView.as_view(), name="index"),
    path("new/", views.ManagerAssistantNewView.as_view(), name="new"),
    path("health/", views.ManagerAssistantHealthView.as_view(), name="health"),
    path("<int:pk>/", views.ManagerAssistantChatView.as_view(), name="chat"),
    path("<int:pk>/delete/", views.ManagerAssistantDeleteView.as_view(), name="delete"),
    path("<int:pk>/stream/", views.ManagerAssistantMessageStreamView.as_view(), name="stream"),
    path("<int:pk>/rename/", views.ManagerAssistantRenameView.as_view(), name="rename"),
    path("customer/quick-start/", views.CustomerAssistantQuickStartView.as_view(), name="customer_quick_start"),
    path("customer/", views.CustomerAssistantIndexView.as_view(), name="customer_index"),
    path("customer/new/", views.CustomerAssistantNewView.as_view(), name="customer_new"),
    path("customer/health/", views.CustomerAssistantHealthView.as_view(), name="customer_health"),
    path("customer/<int:pk>/", views.CustomerAssistantChatView.as_view(), name="customer_chat"),
    path("customer/<int:pk>/delete/", views.CustomerAssistantDeleteView.as_view(), name="customer_delete"),
    path("customer/<int:pk>/stream/", views.CustomerAssistantMessageStreamView.as_view(), name="customer_stream"),
    path("customer/<int:pk>/rename/", views.CustomerAssistantRenameView.as_view(), name="customer_rename"),
    path("staff/quick-start/", views.StaffAssistantQuickStartView.as_view(), name="staff_quick_start"),
    path("staff/", views.StaffAssistantIndexView.as_view(), name="staff_index"),
    path("staff/new/", views.StaffAssistantNewView.as_view(), name="staff_new"),
    path("staff/health/", views.StaffAssistantHealthView.as_view(), name="staff_health"),
    path("staff/<int:pk>/", views.StaffAssistantChatView.as_view(), name="staff_chat"),
    path("staff/<int:pk>/delete/", views.StaffAssistantDeleteView.as_view(), name="staff_delete"),
    path("staff/<int:pk>/stream/", views.StaffAssistantMessageStreamView.as_view(), name="staff_stream"),
    path("staff/<int:pk>/rename/", views.StaffAssistantRenameView.as_view(), name="staff_rename"),
    path("manager/", views.ManagerAssistantIndexView.as_view(), name="manager_index"),
    path("manager/new/", views.ManagerAssistantNewView.as_view(), name="manager_new"),
    path("manager/health/", views.ManagerAssistantHealthView.as_view(), name="manager_health"),
    path("manager/<int:pk>/", views.ManagerAssistantChatView.as_view(), name="manager_chat"),
    path("manager/<int:pk>/delete/", views.ManagerAssistantDeleteView.as_view(), name="manager_delete"),
    path("manager/<int:pk>/stream/", views.ManagerAssistantMessageStreamView.as_view(), name="manager_stream"),
    path("manager/<int:pk>/rename/", views.ManagerAssistantRenameView.as_view(), name="manager_rename"),
]
