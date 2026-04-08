class TargetsPolicy:
    """
    Executive + superuser: xem tất cả, thiết lập KPI.
    Manager: xem tất cả, thiết lập KPI.
    Sales: chỉ xem KPI của chính mình.
    """

    EXECUTIVE_GROUPS = {"Executive", "Executives"}
    MANAGER_GROUPS   = {"Manager", "Managers"}
    SALES_GROUPS     = {"Sales Team", "Sales"}

    @classmethod
    def _auth(cls, user) -> bool:
        return bool(user and user.is_authenticated)

    @classmethod
    def is_executive(cls, user) -> bool:
        return (
            cls._auth(user)
            and (user.is_superuser or user.groups.filter(name__in=cls.EXECUTIVE_GROUPS).exists())
        )

    @classmethod
    def is_manager(cls, user) -> bool:
        return (
            cls._auth(user)
            and (user.is_superuser or user.groups.filter(name__in=cls.MANAGER_GROUPS).exists())
        )

    @classmethod
    def can_view_all(cls, user) -> bool:
        return cls.is_executive(user) or cls.is_manager(user)

    @classmethod
    def can_manage(cls, user) -> bool:
        """Tạo / sửa / xóa KPI."""
        return cls.can_view_all(user)

    @classmethod
    def can_view_own(cls, user) -> bool:
        return cls._auth(user)
