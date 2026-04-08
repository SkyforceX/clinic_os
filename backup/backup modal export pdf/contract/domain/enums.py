from enum import Enum


class ContractStatus(str, Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    FINISHED = "FINISHED"
    TERMINATED = "TERMINATED"
    CANCELLED = "CANCELLED"

    @classmethod
    def from_legacy(cls, contract):
        if getattr(contract, "is_terminated", False):
            return cls.TERMINATED
        if getattr(contract, "is_finished", False):
            return cls.FINISHED
        if getattr(contract, "is_approved", False):
            return cls.APPROVED
        return cls.SUBMITTED