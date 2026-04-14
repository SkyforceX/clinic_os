class AnalyticsPolicy:
    """
    Chỉ user thuộc group Executive (hoặc superuser) mới xem được thống kê.
    Superuser luôn có quyền.
    """

    EXECUTIVE_GROUP_NAMES = {"Executives", "Executive"}

    @classmethod
    def can_view(cls, user) -> bool:
        if not (user and user.is_authenticated):
            return False
        if user.is_superuser:
            return True
        return user.groups.filter(name__in=cls.EXECUTIVE_GROUP_NAMES).exists()
