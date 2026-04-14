"""
apps/reception/policies.py
============================
Kiểm soát quyền truy cập công cụ check-in.
"""

CHECKIN_ALLOWED_GROUPS = {
    "Medical Secretary",
    "Operations Team",
    "Receptionist",
    "HR Admin",
    "HR",
    "Manager",
    "Managers",
    "Executive",
    "Executives",
    "Superuser",
    "Admin",
}

SESSION_KEY = "reception_operator_id"


class ReceptionPolicy:

    @classmethod
    def can_access_checkin_tool(cls, user) -> bool:
        """Kiểm tra user có quyền dùng công cụ check-in không."""
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        return user.groups.filter(name__in=CHECKIN_ALLOWED_GROUPS).exists()

    @classmethod
    def is_authenticated_in_session(cls, request) -> bool:
        """Kiểm tra session check-in tool đã đăng nhập chưa."""
        return bool(request.session.get(SESSION_KEY))

    @classmethod
    def get_operator_id_from_session(cls, request):
        return request.session.get(SESSION_KEY)

    @classmethod
    def set_session(cls, request, user_id: int):
        request.session[SESSION_KEY] = user_id
        request.session.set_expiry(43200)  # 12 giờ

    @classmethod
    def clear_session(cls, request):
        request.session.pop(SESSION_KEY, None)
