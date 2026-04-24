class AuthenticationPolicy:
    @classmethod
    def get_staff_redirect_name(cls, user):
        if not user or not user.is_authenticated:
            return "authentication:staff_login"
        return "dashboard:overview"

    @classmethod
    def can_access_patient_session(cls, request):
        return bool(request.session.get("his_patient_sync_id"))
