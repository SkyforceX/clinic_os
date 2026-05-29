class SchedulingPolicy:
    MANAGER_GROUP_NAMES = {"Managers", "Manager"}
    EXECUTIVE_GROUP_NAMES = {"Executives", "Executive"}
    IT_STAFF_GROUP_NAMES = {"IT Staff", "IT Admin", "IT", "IT Support"}

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
    def is_executive(cls, user):
        if not cls.is_authenticated_actor(user):
            return False
        if user.is_superuser:
            return True
        return user.groups.filter(name__in=cls.EXECUTIVE_GROUP_NAMES).exists()

    @classmethod
    def is_it_staff(cls, user):
        if not cls.is_authenticated_actor(user):
            return False
        if user.is_superuser:
            return True
        return user.groups.filter(name__in=cls.IT_STAFF_GROUP_NAMES).exists()

    @classmethod
    def can_view_schedule_table(cls, user):
        return cls.is_authenticated_actor(user)

    @classmethod
    def can_manage_quote_schedule(cls, user, owner_user_id):
        if not cls.is_authenticated_actor(user):
            return False
        if cls.is_manager(user) or cls.is_executive(user):
            return True
        return owner_user_id == user.id

    @classmethod
    def can_manage_contract_schedule(cls, user, contract):
        if not cls.is_authenticated_actor(user):
            return False
        if cls.is_manager(user) or cls.is_executive(user):
            return True
        return getattr(contract, "created_by_id", None) == user.id

    @classmethod
    def can_redistribute_slots(cls, user, contract):
        return cls.can_manage_contract_schedule(user, contract)

    @classmethod
    def can_end_schedule(cls, user, owner_user_id):
        if not cls.is_authenticated_actor(user):
            return False
        if cls.is_manager(user) or cls.is_executive(user):
            return True
        return owner_user_id == user.id

    @classmethod
    def can_manage_general_settings(cls, user):
        return cls.is_manager(user) or cls.is_executive(user)

    @classmethod
    def can_manage_special_exam_categories(cls, user):
        return cls.is_it_staff(user) or cls.is_executive(user)

    @classmethod
    def can_cleanup_slot_registrations(cls, user):
        return cls.is_it_staff(user)
