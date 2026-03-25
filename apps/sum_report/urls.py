from django.urls import path
from . import views

app_name = 'sum_report'

urlpatterns = [
    path('create', views.create_summary_report, name='create_summary_report'),
]
