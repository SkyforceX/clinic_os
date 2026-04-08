class MeetingDomainError(Exception):
    """Base exception cho domain meeting."""


class MeetingValidationError(MeetingDomainError):
    """Lỗi validate nghiệp vụ buổi họp."""


class MeetingPermissionDenied(MeetingDomainError):
    """Actor không có quyền thực hiện hành động với buổi họp."""


class MeetingNotFound(MeetingDomainError):
    """Không tìm thấy buổi họp hoặc thực thể liên quan."""


class MeetingStateError(MeetingDomainError):
    """Trạng thái buổi họp không hợp lệ cho hành động hiện tại."""


class DeptAssignmentError(MeetingDomainError):
    """Lỗi liên quan phân công phòng ban."""


class StepAdvanceError(MeetingDomainError):
    """Không thể chuyển bước do còn mục chưa xác nhận."""
