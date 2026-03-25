class AuthenticationPolicy:
    STAFF_REDIRECTS = (
        ("Sales Team", "contract:contract_list"),
        ("Operations Team", "contract:contract_list"),
        ("Internal medicine", "clinical:sum_assistant"),
    )

    @classmethod
    def get_staff_redirect_name(cls, user):
        if not user or not user.is_authenticated:
            return "authentication:staff_login"

        for group_name, route_name in cls.STAFF_REDIRECTS:
            if user.groups.filter(name=group_name).exists():
                return route_name

        return "clinical:clinical_dashboard"

    @classmethod
    def can_access_patient_session(cls, request):
        return bool(request.session.get("patient_id"))