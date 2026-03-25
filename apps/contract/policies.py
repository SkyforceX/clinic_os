class ContractPolicy:
    MANAGER_GROUP_NAMES = {"Manager", "Managers"}
    NURSE_GROUP_NAMES = {"Nurses"}

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
    def is_nurse(cls, user):
        if not cls.is_authenticated_actor(user):
            return False
        return user.groups.filter(name__in=cls.NURSE_GROUP_NAMES).exists()

    @classmethod
    def can_view_list(cls, user):
        return cls.is_authenticated_actor(user)

    @classmethod
    def can_create(cls, user):
        return cls.is_authenticated_actor(user)

    @classmethod
    def can_view(cls, user, contract):
        if not cls.is_authenticated_actor(user):
            return False
        if cls.is_manager(user):
            return True
        return getattr(contract, "created_by_id", None) == user.id

    @classmethod
    def can_update(cls, user, contract):
        if not cls.can_view(user, contract):
            return False
        return not getattr(contract, "is_approved", False)

    @classmethod
    def can_delete(cls, user, contract):
        return cls.can_view(user, contract)

    @classmethod
    def can_approve(cls, user, contract):
        if not cls.is_manager(user):
            return False
        return not getattr(contract, "is_approved", False)