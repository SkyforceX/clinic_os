from django import forms


class PatientLoginForm(forms.Form):
    patient_code = forms.CharField(
        label="Mã khách hàng",
        widget=forms.TextInput(
            attrs={
                "id": "id_patient_code",
                "style": "text-transform: uppercase;",
                "autocomplete": "off",
            }
        ),
    )
    password = forms.CharField(
        label="Mật khẩu",
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    def clean_patient_code(self):
        return (self.cleaned_data.get("patient_code") or "").strip().upper()


class ForgotPasswordForm(forms.Form):
    patient_code = forms.CharField(
        label="Mã khách hàng",
        widget=forms.TextInput(
            attrs={
                "id": "id_patient_code",
                "style": "text-transform: uppercase;",
                "autocomplete": "off",
            }
        ),
    )
    phone = forms.CharField(label="Số điện thoại", max_length=15)

    def clean_patient_code(self):
        return (self.cleaned_data.get("patient_code") or "").strip().upper()

    def clean_phone(self):
        return str(self.cleaned_data.get("phone") or "").strip()


class OtpVerifyForm(forms.Form):
    patient_code = forms.CharField(widget=forms.HiddenInput())
    phone = forms.CharField(widget=forms.HiddenInput())
    otp = forms.CharField(label="Mã xác thực OTP", max_length=8)

    def clean_otp(self):
        return str(self.cleaned_data.get("otp") or "").strip()


class ResetPasswordForm(forms.Form):
    patient_code = forms.CharField(widget=forms.HiddenInput())
    phone = forms.CharField(widget=forms.HiddenInput())
    new_password = forms.CharField(
        label="Mật khẩu mới",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        min_length=6,
    )
    new_password2 = forms.CharField(
        label="Nhập lại mật khẩu",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        min_length=6,
    )
    otp = forms.CharField(widget=forms.HiddenInput(), required=False)

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("new_password") != cleaned_data.get("new_password2"):
            self.add_error("new_password2", "Mật khẩu nhập lại không khớp")
        return cleaned_data


class StaffLoginForm(forms.Form):
    username = forms.CharField(
        label="Tên đăng nhập",
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Tên đăng nhập",
                "autocomplete": "username",
                "class": "form-control",
            }
        ),
    )
    password = forms.CharField(
        label="Mật khẩu",
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "Mật khẩu",
                "autocomplete": "current-password",
                "class": "form-control",
            }
        ),
    )