class OrganizationPolicy:
    MANAGER_GROUP_NAMES = {"Managers", "Manager"}
    EXECUTIVE_GROUP_NAMES = {"Executives", "Executive"}

    @classmethod
    def is_manager(cls, user):
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        return user.groups.filter(name__in=cls.MANAGER_GROUP_NAMES).exists()

    @classmethod
    def is_executive(cls, user):
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        return user.groups.filter(name__in=cls.EXECUTIVE_GROUP_NAMES).exists()

    @classmethod
    def can_view_list(cls, user):
        return bool(user and user.is_authenticated)

    @classmethod
    def can_create(cls, user):
        return bool(user and user.is_authenticated)

    @classmethod
    def can_view_company(cls, user, company):
        if not user or not user.is_authenticated:
            return False
        if cls.is_manager(user) or cls.is_executive(user):
            return True
        return company.created_by_id == user.id

    @classmethod
    def can_update_company(cls, user, company):
        return cls.can_view_company(user, company)

    @classmethod
    def can_delete_company(cls, user, company):
        return cls.can_view_company(user, company)
