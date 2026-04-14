class RetentionPolicy:
    EXECUTIVE_GROUPS = {"Executives", "Executive"}
    MANAGER_GROUPS   = {"Managers", "Manager"}

    @classmethod
    def can_view(cls, user) -> bool:
        if not (user and user.is_authenticated):
            return False
        return (
            user.is_superuser
            or user.groups.filter(name__in=cls.EXECUTIVE_GROUPS | cls.MANAGER_GROUPS).exists()
        )
