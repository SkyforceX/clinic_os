"""
helpdesk/policies.py
=====================
Phân quyền hệ thống ticket IT:

- Executive / Executives  : tạo ticket, xem ticket của mình, xác nhận đóng
- IT Admin / IT           : xem tất cả ticket, reply, đổi trạng thái, assign
- Manager / superuser     : xem tất cả ticket (read-only + reply)
"""

from django.contrib.auth import get_user_model

User = get_user_model()

EXECUTIVE_GROUPS = {"Executives", "Executive"}
IT_GROUPS        = {"IT Admin", "IT", "IT Support"}
MANAGER_GROUPS   = {"Managers", "Manager"}


class HelpdeskPolicy:

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
    def is_it_admin(cls, user) -> bool:
        return cls._auth(user) and (
            user.is_superuser
            or user.groups.filter(name__in=IT_GROUPS).exists()
        )

    @classmethod
    def is_manager(cls, user) -> bool:
        return cls._auth(user) and (
            user.is_superuser
            or user.groups.filter(name__in=MANAGER_GROUPS).exists()
        )

    @classmethod
    def can_create_ticket(cls, user) -> bool:
        """Executives tạo ticket."""
        return cls.is_executive(user)

    @classmethod
    def can_view_ticket(cls, user, ticket) -> bool:
        """IT xem tất cả; Executive xem ticket của mình."""
        if not cls._auth(user):
            return False
        if cls.is_it_admin(user) or cls.is_manager(user):
            return True
        return ticket.created_by_id == user.id

    @classmethod
    def can_view_all_tickets(cls, user) -> bool:
        return cls._auth(user) and (cls.is_it_admin(user) or cls.is_manager(user))

    @classmethod
    def can_reply(cls, user, ticket) -> bool:
        """Ai được gửi tin trong ticket (trừ khi đã CLOSED)."""
        if ticket.is_closed:
            return False
        return cls.can_view_ticket(user, ticket)

    @classmethod
    def can_change_status(cls, user, ticket) -> bool:
        """IT Admin đổi status; Executive không được đổi trực tiếp."""
        if ticket.is_closed:
            return False
        return cls.is_it_admin(user)

    @classmethod
    def can_close_ticket(cls, user, ticket) -> bool:
        """Executive (người tạo) xác nhận đóng khi ticket ở PENDING_CONFIRM."""
        if ticket.is_closed:
            return False
        if ticket.status != "PENDING_CONFIRM":
            return False
        return ticket.created_by_id == user.id or cls.is_it_admin(user)

    @classmethod
    def can_assign(cls, user) -> bool:
        return cls.is_it_admin(user)

    @classmethod
    def get_it_users(cls):
        """Danh sách user thuộc nhóm IT để assign."""
        return (
            User.objects.filter(
                groups__name__in=IT_GROUPS,
                is_active=True,
            )
            .distinct()
            .order_by("first_name", "last_name")
        )
