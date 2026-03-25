class ContractDomainError(Exception):
    """Base exception cho domain contracts."""


class ContractValidationError(ContractDomainError):
    """Lỗi validate nghiệp vụ hợp đồng."""


class ContractPermissionDenied(ContractDomainError):
    """Actor không có quyền thực hiện hành động với hợp đồng."""


class ContractNotFound(ContractDomainError):
    """Không tìm thấy hợp đồng hoặc thực thể liên quan."""


class ContractStateError(ContractDomainError):
    """Trạng thái hợp đồng không hợp lệ cho hành động hiện tại."""