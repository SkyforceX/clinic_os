"""
tasks/policies.py
==================
Phân quyền giao việc:

- Executive / superuser:  tạo task giao cho bất kỳ user nào
- Trưởng phòng Nhân sự (HR Admin/Lead):  tạo task giao cho bất kỳ user nào
- Trưởng phòng (Manager):  tạo task giao cho nhân viên trực thuộc mình
- Nhân viên (Staff):  xem và cập nhật tiến độ task được giao cho mình

Nhận diện "Trưởng phòng" = user có group Managers hoặc có ít nhất 1 nhân viên
trong Employee.direct_manager trỏ đến mình.
"""

from django.contrib.auth import get_user_model

User = get_user_model()

EXECUTIVE_GROUPS = {"Executive", "Executives"}
MANAGER_GROUPS   = {"Manager", "Managers"}
HR_ADMIN_GROUPS  = {"HR Admin", "HR", "HR Lead", "Trưởng phòng Nhân sự"}


class TaskPolicy:

    @classmethod
    def _auth(cls, user) -> bool:
        return bool(user and user.is_authenticated)

    @classmethod
    def is_executive(cls, user) -> bool:
        return cls._auth(user) and (
            user.is_superuser
            or user.groups.filter(name__in=EXECUTIVE_GROUPS).exists()
        )

    @classmethod
    def is_hr_admin(cls, user) -> bool:
        return cls._auth(user) and (
            user.is_superuser
            or user.groups.filter(name__in=HR_ADMIN_GROUPS).exists()
        )

    @classmethod
    def is_manager(cls, user) -> bool:
        return cls._auth(user) and (
            user.is_superuser
            or user.groups.filter(name__in=MANAGER_GROUPS).exists()
        )

    @classmethod
    def is_department_head(cls, user) -> bool:
        """Trưởng phòng = Manager group HOẶC có nhân viên báo cáo trực tiếp."""
        if not cls._auth(user):
            return False
        if cls.is_executive(user) or cls.is_hr_admin(user) or cls.is_manager(user):
            return True
        # Kiểm tra HRM: user có direct_reports không
        try:
            from apps.hrm.models import Employee
            return Employee.objects.filter(
                direct_manager__user=user,
                status="ACTIVE",
            ).exists()
        except Exception:
            return False

    @classmethod
    def can_create_task(cls, user) -> bool:
        """Executive, HR Admin, Trưởng phòng đều tạo được task."""
        return cls._auth(user) and (
            cls.is_executive(user)
            or cls.is_hr_admin(user)
            or cls.is_department_head(user)
        )

    @classmethod
    def get_assignable_users(cls, user):
        """
        Trả về QuerySet User có thể được giao việc bởi `user`.

        - Executive / HR Admin → tất cả user active trong hệ thống
        - Trưởng phòng (Manager group) → tất cả user active
        - Trưởng phòng (chỉ có direct_reports) → chỉ direct reports + bản thân
        """
        if not cls.can_create_task(user):
            return User.objects.none()

        if cls.is_executive(user) or cls.is_hr_admin(user) or cls.is_manager(user):
            return (
                User.objects.filter(is_active=True)
                .select_related("employee_profile")
                .order_by("first_name", "last_name", "username")
            )

        # Chỉ là trưởng phòng thông qua direct_reports
        try:
            from apps.hrm.models import Employee
            report_user_ids = list(
                Employee.objects.filter(
                    direct_manager__user=user,
                    status="ACTIVE",
                ).values_list("user_id", flat=True)
            )
            report_user_ids = [uid for uid in report_user_ids if uid]
            report_user_ids.append(user.id)
            return (
                User.objects.filter(id__in=report_user_ids, is_active=True)
                .order_by("first_name", "last_name", "username")
            )
        except Exception:
            return User.objects.filter(id=user.id)

    @classmethod
    def can_view_task(cls, user, task) -> bool:
        """Ai được xem task: creator, assignee, watcher, executive, manager."""
        if not cls._auth(user):
            return False
        if cls.is_executive(user) or cls.is_hr_admin(user) or cls.is_manager(user):
            return True
        if task.created_by_id == user.id:
            return True
        if task.assignee_id == user.id:
            return True
        return task.watchers.filter(id=user.id).exists()

    @classmethod
    def can_edit_task(cls, user, task) -> bool:
        """Creator và executive/manager có thể sửa."""
        if not cls._auth(user):
            return False
        if cls.is_executive(user) or cls.is_hr_admin(user) or cls.is_manager(user):
            return True
        return task.created_by_id == user.id

    @classmethod
    def can_update_stage(cls, user, task) -> bool:
        """Assignee, creator, manager có thể kéo task sang stage khác."""
        if not cls._auth(user):
            return False
        if cls.is_executive(user) or cls.is_hr_admin(user) or cls.is_manager(user):
            return True
        return task.created_by_id == user.id or task.assignee_id == user.id

    @classmethod
    def can_delete_task(cls, user, task) -> bool:
        """Chỉ Executive, HR Admin và creator mới xóa được."""
        if not cls._auth(user):
            return False
        if cls.is_executive(user) or cls.is_hr_admin(user):
            return True
        return task.created_by_id == user.id

    @classmethod
    def can_view_all_tasks(cls, user) -> bool:
        """Executive / HR Admin / Manager xem tất cả. Nhân viên chỉ xem task liên quan."""
        return (
            cls._auth(user)
            and (cls.is_executive(user) or cls.is_hr_admin(user) or cls.is_manager(user))
        )
