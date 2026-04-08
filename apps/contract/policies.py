class ContractPolicy:
    MANAGER_GROUP_NAMES = {"Manager", "Managers"}
    NURSE_GROUP_NAMES = {"Nurses"}
    EXECUTIVE_GROUP_NAMES = {"Executive", "Executives"}

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
    def is_executive(cls, user):
        if not cls.is_authenticated_actor(user):
            return False
        if user.is_superuser:
            return True
        return user.groups.filter(name__in=cls.EXECUTIVE_GROUP_NAMES).exists()

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
        return not getattr(contract, "is_approved", False) and not getattr(contract, "is_locked", False)

    @classmethod
    def can_delete(cls, user, contract):
        if not cls.can_view(user, contract):
            return False
        return not getattr(contract, "is_locked", False)

    @classmethod
    def can_approve(cls, user, contract):
        if not cls.is_manager(user):
            return False
        return not getattr(contract, "is_approved", False) and not getattr(contract, "is_locked", False)

    @classmethod
    def can_view_implementation(cls, user):
        return cls.is_authenticated_actor(user)

    @classmethod
    def can_edit_implementation(cls, user, contract):
        if not cls.is_authenticated_actor(user):
            return False
        return getattr(contract, "created_by_id", None) == user.id

    @classmethod
    def can_manage_implementation_unlock(cls, user, contract):
        return cls.can_edit_implementation(user, contract)

    @classmethod
    def can_view_implementation_logs(cls, user, contract):
        if not cls.is_authenticated_actor(user):
            return False
        if user.is_superuser or cls.is_executive(user):
            return True
        return getattr(contract, "created_by_id", None) == user.id

    @classmethod
    def can_view_implementation_contract_link(cls, user, contract):
        if not cls.is_authenticated_actor(user):
            return False
        if cls.is_executive(user):
            return True
        return getattr(contract, "created_by_id", None) == user.id
