from django.urls import path
from apps.helpdesk.web.views.ticket_views import ticket_list, ticket_create, ticket_detail

app_name = "helpdesk"

urlpatterns = [
    path("",            ticket_list,   name="list"),
    path("new/",        ticket_create, name="create"),
    path("<int:ticket_id>/", ticket_detail, name="detail"),
]
