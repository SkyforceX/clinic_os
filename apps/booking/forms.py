from django import forms
from django.contrib.auth.models import User

class LoginForm(forms.Form):
    username = forms.CharField(label='Tên đăng nhập')
    password = forms.CharField(widget=forms.PasswordInput, label='Mật khẩu')


class UserForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, label='Mật khẩu')

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password']


class PatientLoginForm(forms.Form):
    ma_bn = forms.CharField(label='Mã BN', max_length=20)
    ho_ten = forms.CharField(label='Họ tên', max_length=100)
