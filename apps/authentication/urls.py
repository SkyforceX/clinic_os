from django.urls import path
from . import views

app_name = 'authentication'

urlpatterns = [
    path('', views.patient_login, name='patient_login'),
    path('patient/dashboard/', views.patient_dashboard, name='patient_dashboard'),
    path('staff/', views.staff_login, name='staff_login'),
    path('staff-logout/', views.staff_logout, name='staff_logout'),
    path('dang-xuat/', views.patient_logout, name='patient_logout'),
    path('quen-mat-khau/', views.request_password_reset, name='forgot_password'),
    path('xac-thuc-otp/', views.verify_otp, name='verify_otp'),
    path('dat-lai-mat-khau/', views.reset_password, name='reset_password'),
]