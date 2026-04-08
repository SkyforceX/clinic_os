class EngagementPolicy:
    ADMIN_GROUPS    = {"Manager", "Managers", "Engagement Lead", "Engagement Admin"}
    AGENT_GROUPS    = {"Engagement Agent", "Engagement Team", "Sales Team", "Sales"}
    EXECUTIVE_GROUPS = {"Executive", "Executives"}

    @classmethod
    def _auth(cls, user) -> bool:
        return bool(user and user.is_authenticated)

    @classmethod
    def is_engagement_admin(cls, user) -> bool:
        return (
            cls._auth(user)
            and (user.is_superuser or user.groups.filter(name__in=cls.ADMIN_GROUPS).exists())
        )

    @classmethod
    def is_agent(cls, user) -> bool:
        return (
            cls._auth(user)
            and (cls.is_engagement_admin(user) or user.groups.filter(name__in=cls.AGENT_GROUPS).exists())
        )

    @classmethod
    def can_upload_list(cls, user) -> bool:
        """Chỉ admin mới được upload danh sách liên hệ."""
        return cls.is_engagement_admin(user)

    @classmethod
    def can_view_full_phone(cls, user, contact_list=None) -> bool:
        """
        Xem số điện thoại đầy đủ:
        - superuser: luôn có
        - user trong allow_full_phone_groups của list: có
        - Engagement Admin không thuộc list: không
        """
        if not cls._auth(user):
            return False
        if user.is_superuser:
            return True
        if contact_list is None:
            return cls.is_engagement_admin(user)
        allowed_groups = list(contact_list.allow_full_phone_groups or [])
        if not allowed_groups:
            # Không cấu hình → chỉ superuser (đã xử lý trên)
            return False
        return user.groups.filter(name__in=allowed_groups).exists()

    @classmethod
    def can_manage_channels(cls, user) -> bool:
        return cls.is_engagement_admin(user)

    @classmethod
    def can_view_stats(cls, user) -> bool:
        return (
            cls._auth(user)
            and (
                user.is_superuser
                or user.groups.filter(
                    name__in=cls.ADMIN_GROUPS | cls.EXECUTIVE_GROUPS
                ).exists()
            )
        )

    @classmethod
    def can_assign_contacts(cls, user) -> bool:
        return cls.is_engagement_admin(user)
