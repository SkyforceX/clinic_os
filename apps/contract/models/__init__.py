"""
Transitional model facade for contract domain.

Refactor hiện tại:
- Contract vẫn đang dùng bảng/model legacy của apps.booking
- Quotation vẫn đang dùng bảng/model legacy của apps.booking
- CorporateContractProfile đã được đưa về app mới apps.contract
"""

from apps.booking.models import (
    BloodCollectionInfo as BloodCollectionPlan,
    ContractServiceDetail as ContractServiceLine,
    HealthContract as Contract,
    QuotationDraft,
    QuotationDraftDetail as QuotationLine,
)

from apps.contract.domain.enums import ContractStatus
from apps.contract.models.corporate import CorporateContractProfile

__all__ = [
    "Contract",
    "ContractServiceLine",
    "BloodCollectionPlan",
    "QuotationDraft",
    "QuotationLine",
    "CorporateContractProfile",
    "ContractStatus",
]