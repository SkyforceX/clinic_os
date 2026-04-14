from django.urls import path
from . import views

urlpatterns = [
    path('', views.procedure_list, name='list'),
    path('tao/', views.procedure_create, name='create'),
    path('<int:pk>/', views.procedure_detail, name='detail'),
    path('<int:pk>/sua/', views.procedure_edit, name='edit'),
    path('<int:pk>/xoa/', views.procedure_delete, name='delete'),
    # Steps AJAX
    path('<int:procedure_pk>/buoc/tao/', views.step_create, name='step_create'),
    path('buoc/<int:step_pk>/sua/', views.step_edit, name='step_edit'),
    path('buoc/<int:step_pk>/xoa/', views.step_delete, name='step_delete'),
    # Attachments AJAX
    path('<int:procedure_pk>/dinh-kem/tai-len/', views.attachment_upload, name='attachment_upload'),
    path('dinh-kem/<int:attachment_pk>/xoa/', views.attachment_delete, name='attachment_delete'),
]
