class HRMPolicy:
    """
    Policy phân quyền cho app hr.

    Group HR_ADMIN: toàn quyền (tạo, sửa, xóa nhân viên, cấp quyền).
    Group Managers: xem toàn bộ, sửa trạng thái.
    Mọi user đăng nhập: xem hồ sơ của chính mình.
    """

    HR_ADMIN_GROUP_NAMES  = {"HR Admins", "HR Admin", "HR"}
    MANAGER_GROUP_NAMES   = {"Managers", "Manager"}

    @classmethod
    def is_authenticated_actor(cls, user) -> bool:
        return bool(user and user.is_authenticated)

    @classmethod
    def is_hr_admin(cls, user) -> bool:
        if not cls.is_authenticated_actor(user):
            return False
        if user.is_superuser:
            return True
        return user.groups.filter(name__in=cls.HR_ADMIN_GROUP_NAMES).exists()

    @classmethod
    def is_manager(cls, user) -> bool:
        if not cls.is_authenticated_actor(user):
            return False
        if user.is_superuser:
            return True
        return user.groups.filter(name__in=cls.MANAGER_GROUP_NAMES).exists()

    # ── Nhân viên ─────────────────────────────────────────────────────────────

    @classmethod
    def can_view_employee_list(cls, user) -> bool:
        return cls.is_hr_admin(user) or cls.is_manager(user)

    @classmethod
    def can_view_employee(cls, user, employee) -> bool:
        """HR Admin / Manager xem tất cả; nhân viên xem hồ sơ của chính mình."""
        if not cls.is_authenticated_actor(user):
            return False
        if cls.is_hr_admin(user) or cls.is_manager(user):
            return True
        return getattr(employee, "user_id", None) == user.pk

    @classmethod
    def can_create_employee(cls, user) -> bool:
        return cls.is_hr_admin(user)

    @classmethod
    def can_update_employee(cls, user) -> bool:
        return cls.is_hr_admin(user)

    @classmethod
    def can_delete_employee(cls, user) -> bool:
        return user.is_superuser

    # ── Onboard / Offboard / Transfer ─────────────────────────────────────────

    @classmethod
    def can_onboard(cls, user) -> bool:
        return cls.is_hr_admin(user)

    @classmethod
    def can_offboard(cls, user) -> bool:
        return cls.is_hr_admin(user)

    @classmethod
    def can_transfer(cls, user) -> bool:
        return cls.is_hr_admin(user)

    # ── Phòng ban / Chức vụ ───────────────────────────────────────────────────

    @classmethod
    def can_manage_departments(cls, user) -> bool:
        return cls.is_hr_admin(user)

    @classmethod
    def can_manage_positions(cls, user) -> bool:
        return cls.is_hr_admin(user)

    # ── Phân quyền ────────────────────────────────────────────────────────────

    @classmethod
    def can_grant_access(cls, user) -> bool:
        return cls.is_hr_admin(user)

    @classmethod
    def can_view_access_log(cls, user) -> bool:
        return cls.is_hr_admin(user) or cls.is_manager(user)
