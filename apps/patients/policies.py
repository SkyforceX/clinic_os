class PatientPolicy:
    MANAGER_GROUP_NAMES = {"Managers", "Manager"}
    DELETE_ALLOWED_USERNAMES = {"duc.it", "admin93"}

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
    def can_view_patient_list(cls, user):
        return cls.is_authenticated_actor(user)

    @classmethod
    def can_import_patients(cls, user):
        return cls.is_authenticated_actor(user)

    @classmethod
    def can_create_patient(cls, user):
        return cls.is_authenticated_actor(user)

    @classmethod
    def can_update_patient(cls, user):
        return cls.is_manager(user)

    @classmethod
    def can_delete_patient(cls, user):
        if not cls.is_manager(user):
            return False
        return getattr(user, "username", "") in cls.DELETE_ALLOWED_USERNAMES

    @classmethod
    def can_access_company(cls, user, company):
        if not cls.is_authenticated_actor(user):
            return False
        if cls.is_manager(user):
            return True
        return getattr(company, "created_by_id", None) == user.id
