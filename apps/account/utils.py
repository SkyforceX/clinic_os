from django import forms


class ChangePasswordForm(forms.Form):
    current_password = forms.CharField(
        label="Mật khẩu hiện tại",
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )
    new_password = forms.CharField(
        label="Mật khẩu mới",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        min_length=6,
        help_text="Ít nhất 6 ký tự.",
    )
    confirm_password = forms.CharField(
        label="Xác nhận mật khẩu mới",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    def clean(self):
        cleaned = super().clean()
        new_password = cleaned.get("new_password")
        confirm_password = cleaned.get("confirm_password")

        if new_password != confirm_password:
            self.add_error("confirm_password", "Mật khẩu xác nhận không khớp.")

        return cleaned