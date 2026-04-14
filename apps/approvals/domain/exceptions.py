class ApprovalDomainError(Exception):
    """Base exception cho domain approvals."""


class ApprovalValidationError(ApprovalDomainError):
    """Lỗi validate nghiệp vụ."""


class ApprovalPermissionDenied(ApprovalDomainError):
    """Không có quyền thực hiện hành động."""


class ApprovalStateError(ApprovalDomainError):
    """Trạng thái không hợp lệ cho hành động hiện tại."""


class ApprovalNotFound(ApprovalDomainError):
    """Không tìm thấy yêu cầu phê duyệt."""
