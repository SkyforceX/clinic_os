class ClinicalPolicy:
    MANAGER_GROUP_NAMES = {"Managers", "Manager"}

    @classmethod
    def is_authenticated_actor(cls, user):
        return bool(user and user.is_authenticated)

    @classmethod
    def is_manager(cls, user):
        if not cls.is_authenticated_actor(user):
            return False
        if user.is_superuser:
            return True
        return user.groups.filter(name__in=cls.MANAGER_GROUP_NAMES).exists()

    @classmethod
    def can_view_dashboard(cls, user):
        return cls.is_authenticated_actor(user)

    @classmethod
    def can_manage_dental(cls, user):
        return cls.is_authenticated_actor(user)

    @classmethod
    def can_manage_pathology(cls, user):
        return cls.is_authenticated_actor(user)

    @classmethod
    def can_use_sum_assistant(cls, user):
        return cls.can_view_dashboard(user)
