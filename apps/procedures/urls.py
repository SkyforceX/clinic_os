from django.urls import path, include

app_name = 'procedures'

urlpatterns = [
    path('', include('apps.procedures.web.urls')),
]
