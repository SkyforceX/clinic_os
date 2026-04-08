class MeetingPolicy:
    """
    Quyền hạn truy cập tính năng meeting.
    Dùng Group-based authorization nhất quán với ContractPolicy.
    """

    MANAGER_GROUP_NAMES = {"Manager", "Managers"}
    EXECUTIVE_GROUP_NAMES = {"Executive", "Executives"}

    @classmethod
    def _is_authenticated(cls, user) -> bool:
        return bool(user and getattr(user, "is_authenticated", False))

    @classmethod
    def is_manager(cls, user) -> bool:
        if not cls._is_authenticated(user):
            return False
        if getattr(user, "is_superuser", False):
            return True
        return user.groups.filter(name__in=cls.MANAGER_GROUP_NAMES).exists()

    @classmethod
    def is_executive(cls, user) -> bool:
        if not cls._is_authenticated(user):
            return False
        if getattr(user, "is_superuser", False):
            return True
        return user.groups.filter(name__in=cls.EXECUTIVE_GROUP_NAMES).exists()

    # ── Session permissions ───────────────────────────────────────────────

    @classmethod
    def can_create_session(cls, user) -> bool:
        """Bất kỳ user đã đăng nhập đều có thể tạo buổi họp."""
        return cls._is_authenticated(user)

    @classmethod
    def can_view_session(cls, user, session) -> bool:
        if not cls._is_authenticated(user):
            return False
        if cls.is_manager(user):
            return True
        # Người tạo hoặc người tham dự đều xem được
        if getattr(session, "created_by_id", None) == user.pk:
            return True
        return session.participants.filter(user=user).exists()

    @classmethod
    def can_edit_session(cls, user, session) -> bool:
        """
        Tất cả participant có can_edit=True đều chỉnh được
        khi session đang OPEN — thiết kế collaborative editing.
        """
        if not cls.can_view_session(user, session):
            return False
        if not session.is_editable:
            return False
        if cls.is_manager(user):
            return True
        return session.participants.filter(user=user, can_edit=True).exists()

    @classmethod
    def can_advance_step(cls, user, session) -> bool:
        """Chỉ người tạo hoặc manager mới được chuyển bước."""
        if not cls._is_authenticated(user):
            return False
        if cls.is_manager(user):
            return True
        return getattr(session, "created_by_id", None) == user.pk

    @classmethod
    def can_close_session(cls, user, session) -> bool:
        return cls.can_advance_step(user, session)

    @classmethod
    def can_sign_minutes(cls, user, session) -> bool:
        """Người tham dự LEAD hoặc manager đều được ký biên bản."""
        if not cls._is_authenticated(user):
            return False
        if cls.is_manager(user):
            return True
        return session.participants.filter(user=user).exists()

    # ── DeptAssignment permissions ────────────────────────────────────────

    @classmethod
    def can_confirm_dept(cls, user, assignment) -> bool:
        """
        Trưởng phòng (lead_user) hoặc manager xác nhận phân công.
        """
        if not cls._is_authenticated(user):
            return False
        if cls.is_manager(user):
            return True
        return getattr(assignment, "lead_user_id", None) == user.pk

    @classmethod
    def can_view_all_sessions(cls, user) -> bool:
        return cls.is_manager(user)
