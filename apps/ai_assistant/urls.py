from django.urls import path
from . import views

app_name = "ai_assistant"

urlpatterns = [
    path("", views.ConversationListView.as_view(), name="index"),
    path("new/", views.ConversationNewView.as_view(), name="new"),
    path("health/", views.OllamaHealthView.as_view(), name="health"),
    path("<int:pk>/", views.ConversationChatView.as_view(), name="chat"),
    path("<int:pk>/delete/", views.ConversationDeleteView.as_view(), name="delete"),
    path("<int:pk>/stream/", views.MessageStreamView.as_view(), name="stream"),
    path("<int:pk>/rename/", views.ConversationRenameView.as_view(), name="rename"),
]
