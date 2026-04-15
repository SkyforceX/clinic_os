"""
apps/record_completion/policies.py
=====================================
Kiểm soát quyền truy cập cho từng bước hoàn tất hồ sơ.

Mapping bước → nhóm người dùng được phép xác nhận:
  Bước 0 – checklist_review  : Medical Secretary, Secretary, Receptionist
  Bước 1 – nurse_confirm     : Nurse, Nurses
  Bước 2 – doctor_ecg        : Doctor, Doctors, Internal Doctor
  Bước 3 – director_confirm  : Medical Director, Director
  Bước 4 – paper_signed      : Medical Secretary, Secretary, Receptionist
  Bước 5 – dispatched        : Medical Secretary, Secretary, Receptionist

Manager / superuser luôn được làm tất cả các bước.
"""

STEP_ALLOWED_GROUPS = [
    # step 0
    {"Medical Secretary", "Secretary", "Receptionist"},
    # step 1
    {"Nurse", "Nurses"},
    # step 2
    {"Doctor", "Doctors", "Internal Doctor"},
    # step 3
    {"Medical Director", "Director"},
    # step 4
    {"Medical Secretary", "Secretary", "Receptionist"},
    # step 5
    {"Medical Secretary", "Secretary", "Receptionist"},
]

MANAGER_GROUPS = {"Manager", "Managers"}
TOTAL_STEPS = 6


class RecordCompletionPolicy:

    @classmethod
    def can_view(cls, user) -> bool:
        return bool(user and user.is_authenticated)

    @classmethod
    def can_advance_step(cls, user, step_index: int) -> bool:
        """Người dùng có thể xác nhận bước step_index không?"""
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        user_groups = set(user.groups.values_list("name", flat=True))
        if user_groups & MANAGER_GROUPS:
            return True
        if step_index < 0 or step_index >= TOTAL_STEPS:
            return False
        return bool(user_groups & STEP_ALLOWED_GROUPS[step_index])

    @classmethod
    def get_advanceable_steps(cls, user) -> set:
        """Trả về set các index bước mà user có thể xác nhận."""
        if not user or not user.is_authenticated:
            return set()
        if user.is_superuser:
            return set(range(TOTAL_STEPS))
        user_groups = set(user.groups.values_list("name", flat=True))
        if user_groups & MANAGER_GROUPS:
            return set(range(TOTAL_STEPS))
        result = set()
        for i, allowed in enumerate(STEP_ALLOWED_GROUPS):
            if user_groups & allowed:
                result.add(i)
        return result
