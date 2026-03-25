from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect


def _normalize_text(value):
    return str(value or "").strip().lower()


def _norm_gender(value):
    """
    Chuẩn hóa giới tính từ nhiều kiểu dữ liệu legacy về dạng hiển thị ổn định.
    Trả về: 'Nam', 'Nữ', hoặc giá trị gốc đã trim nếu không nhận diện được.
    """
    raw = str(value or "").strip()
    normalized = _normalize_text(value)

    male_values = {
        "nam",
        "male",
        "m",
        "1",
        "true",
        "boy",
    }
    female_values = {
        "nữ",
        "nu",
        "female",
        "f",
        "0",
        "false",
        "girl",
    }

    if normalized in male_values:
        return "Nam"
    if normalized in female_values:
        return "Nữ"
    return raw


def patient_access_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        patient_id = request.session.get("patient_id")
        if not patient_id:
            messages.warning(request, "Vui lòng đăng nhập để tiếp tục.")
            return redirect("authentication:patient_login")
        return view_func(request, *args, **kwargs)

    return _wrapped_view