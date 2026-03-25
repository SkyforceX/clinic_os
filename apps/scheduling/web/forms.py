from django import forms


class DummySchedulingForm(forms.Form):
    """
    Placeholder để giữ cấu trúc app nhất quán.
    Scheduling hiện chủ yếu dùng service + selector, chưa cần form class riêng.
    """
    pass