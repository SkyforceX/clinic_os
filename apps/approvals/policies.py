from apps.contract.policies import ContractPolicy


class ApprovalPolicy:
    """
    Policy cho hệ thống phê duyệt.
    Tái dụng ContractPolicy để giữ nhất quán về định nghĩa group.
    """

    @classmethod
    def can_submit(cls, user, document) -> bool:
        """Mọi user đăng nhập đều có thể nộp tài liệu của mình."""
        return ContractPolicy.is_authenticated_actor(user)

    @classmethod
    def can_view_inbox(cls, user) -> bool:
        """Chỉ Executive (và superuser) xem được inbox."""
        return ContractPolicy.is_executive(user)

    @classmethod
    def can_approve(cls, user, ar) -> bool:
        """
        Executive, request đang PENDING, không tự duyệt chính mình
        (trừ superuser).
        """
        if not ContractPolicy.is_executive(user):
            return False
        if ar.status != "PENDING":
            return False
        if (
            ar.requested_by_id
            and ar.requested_by_id == user.id
            and not user.is_superuser
        ):
            return False
        return True

    @classmethod
    def can_reject(cls, user, ar) -> bool:
        return cls.can_approve(user, ar)

    @classmethod
    def can_recall(cls, user, ar) -> bool:
        """Chỉ người nộp, khi request vẫn PENDING."""
        if not ContractPolicy.is_authenticated_actor(user):
            return False
        if ar.status != "PENDING":
            return False
        return ar.requested_by_id == user.id

    @classmethod
    def can_view_request(cls, user, ar) -> bool:
        if ContractPolicy.is_executive(user):
            return True
        return ar.requested_by_id == user.id
