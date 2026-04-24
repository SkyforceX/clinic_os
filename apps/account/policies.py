class AccountPolicy:
    @classmethod
    def can_view_self_profile(cls, request, patient):
        if not patient:
            return False

        session_patient_id = request.session.get("his_patient_sync_id")
        return bool(session_patient_id and str(session_patient_id) == str(patient.id))

    @classmethod
    def can_change_self_password(cls, request, patient):
        return cls.can_view_self_profile(request, patient)
