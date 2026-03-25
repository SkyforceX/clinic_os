def build_dashboard_context(*, request):
    staff_profile = getattr(request.user, "staff_profile", None)
    return {
        "staff": staff_profile,
    }