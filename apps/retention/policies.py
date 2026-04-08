class RetentionPolicy:
    EXECUTIVE_GROUPS = {"Executive", "Executives"}
    MANAGER_GROUPS   = {"Manager", "Managers"}

    @classmethod
    def can_view(cls, user) -> bool:
        if not (user and user.is_authenticated):
            return False
        return (
            user.is_superuser
            or user.groups.filter(name__in=cls.EXECUTIVE_GROUPS | cls.MANAGER_GROUPS).exists()
        )
