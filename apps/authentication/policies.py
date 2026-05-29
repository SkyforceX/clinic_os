class AuthenticationPolicy:
    @staticmethod
    def _is_superuser(user):
        return bool(getattr(user, "is_superuser", False))

    @classmethod
    def _is_executive(cls, user):
        return cls._is_superuser(user) or user.groups.filter(
            name__in=["Executive", "Executives"]
        ).exists()

    @classmethod
    def _is_it_staff(cls, user):
        return cls._is_superuser(user) or user.groups.filter(
            name__in=["IT Admin", "IT", "IT Support"]
        ).exists()

    @classmethod
    def get_staff_redirect_name(cls, user):
        if not user or not user.is_authenticated:
            return "authentication:staff_login"
        if cls._is_executive(user) or cls._is_it_staff(user):
            return "dashboard:overview"
        return "contract:implementation_plan_list"

    @classmethod
    def can_access_patient_session(cls, request):
        return bool(request.session.get("his_patient_sync_id"))
