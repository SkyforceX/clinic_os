from __future__ import annotations


class ContractPolicy:
    """
    Contract policy theo kiến trúc mới nhưng vẫn giữ compatibility với code cũ.

    Mục tiêu:
    - Hỗ trợ group chuẩn mới:
        Managers
        Executives
        Sales Team
        Accountants
        Nurses
        Doctors
        Operations Team
        Customer Service Team
        HR Admins
        Lab Technicians
        Imaging Technicians
        IT Staff

    - Giữ tương thích với legacy group name:
        Manager
        Executive
        Sales
        Doctor
        Nurse
        Operations
        HR Admin
    """

    MANAGER_GROUP_NAMES = {"Managers", "Manager"}
    EXECUTIVE_GROUP_NAMES = {"Executives", "Executive"}
    SALES_GROUP_NAMES = {"Sales Team", "Sales"}
    ACCOUNTANT_GROUP_NAMES = {"Accountant", "Accountants"}
    NURSE_GROUP_NAMES = {"Nurses", "Nurse"}
    DOCTOR_GROUP_NAMES = {"Doctors", "Doctor"}
    OPERATIONS_GROUP_NAMES = {"Operations Team", "Operations"}
    CUSTOMER_SERVICE_GROUP_NAMES = {"Customer Service", "Customer Service Team", "CSKH"}
    HR_ADMIN_GROUP_NAMES = {"HR Admins", "HR Admin"}
    LAB_TECHNICIAN_GROUP_NAMES = {"Lab Technician", "Lab Technicians"}
    IMAGING_TECHNICIAN_GROUP_NAMES = {"Imaging Technician", "Imaging Technicians"}
    IT_STAFF_GROUP_NAMES = {"IT Staff"}

    @classmethod
    def is_authenticated_actor(cls, user):
        return bool(user and getattr(user, "is_authenticated", False))

    @classmethod
    def _has_group(cls, user, group_names):
        if not cls.is_authenticated_actor(user):
            return False
        if getattr(user, "is_superuser", False):
            return True
        try:
            return user.groups.filter(name__in=group_names).exists()
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Role checks
    # ------------------------------------------------------------------
    @classmethod
    def is_manager(cls, user):
        return cls._has_group(user, cls.MANAGER_GROUP_NAMES)

    @classmethod
    def is_executive(cls, user):
        return cls._has_group(user, cls.EXECUTIVE_GROUP_NAMES)

    @classmethod
    def is_sales(cls, user):
        return cls._has_group(user, cls.SALES_GROUP_NAMES)

    @classmethod
    def is_accountant(cls, user):
        return cls._has_group(user, cls.ACCOUNTANT_GROUP_NAMES)

    @classmethod
    def is_nurse(cls, user):
        return cls._has_group(user, cls.NURSE_GROUP_NAMES)

    @classmethod
    def is_doctor(cls, user):
        return cls._has_group(user, cls.DOCTOR_GROUP_NAMES)

    @classmethod
    def is_operations(cls, user):
        return cls._has_group(user, cls.OPERATIONS_GROUP_NAMES)

    @classmethod
    def is_customer_service(cls, user):
        return cls._has_group(user, cls.CUSTOMER_SERVICE_GROUP_NAMES)

    @classmethod
    def is_hr_admin(cls, user):
        return cls._has_group(user, cls.HR_ADMIN_GROUP_NAMES)

    @classmethod
    def is_lab_technician(cls, user):
        return cls._has_group(user, cls.LAB_TECHNICIAN_GROUP_NAMES)

    @classmethod
    def is_imaging_technician(cls, user):
        return cls._has_group(user, cls.IMAGING_TECHNICIAN_GROUP_NAMES)

    @classmethod
    def is_it_staff(cls, user):
        return cls._has_group(user, cls.IT_STAFF_GROUP_NAMES)

    @classmethod
    def can_view_contracts(cls, user):
        """
        Hàm mới: quyền xem danh sách / module contract.
        """
        return cls.is_authenticated_actor(user)

    @classmethod
    def can_view_list(cls, user):
        """
        Legacy compatibility.
        """
        return cls.can_view_contracts(user)

    @classmethod
    def can_create_contract(cls, user):
        """
        Hàm mới: quyền tạo báo giá / hợp đồng.
        """
        if not cls.is_authenticated_actor(user):
            return False
        if getattr(user, "is_superuser", False):
            return True
        return cls.is_sales(user) or cls.is_manager(user) or cls.is_executive(user)

    @classmethod
    def can_create(cls, user):
        """
        Legacy compatibility.
        """
        return cls.can_create_contract(user)

    @classmethod
    def can_view_contract_detail(cls, user, contract):
        """
        Hàm mới: xem chi tiết contract.
        """
        if not cls.is_authenticated_actor(user):
            return False

        if getattr(user, "is_superuser", False):
            return True

        if cls.is_manager(user) or cls.is_executive(user):
            return True

        return getattr(contract, "created_by_id", None) == getattr(user, "id", None)

    @classmethod
    def can_view(cls, user, contract):
        """
        Legacy compatibility.
        """
        return cls.can_view_contract_detail(user, contract)

    @classmethod
    def can_edit_contract(cls, user, contract):
        """
        Hàm mới: sửa hợp đồng.
        """
        if not cls.can_view_contract_detail(user, contract):
            return False

        if getattr(user, "is_superuser", False):
            return True

        if cls.is_manager(user):
            return True

        return (
            cls.is_sales(user)
            and getattr(contract, "created_by_id", None) == getattr(user, "id", None)
            and not getattr(contract, "is_approved", False)
            and not getattr(contract, "is_locked", False)
        )

    @classmethod
    def can_update(cls, user, contract):
        """
        Legacy compatibility.
        """
        return cls.can_edit_contract(user, contract)

    @classmethod
    def can_delete_contract(cls, user, contract):
        """
        Hàm mới: xóa hợp đồng.
        """
        if not cls.can_view_contract_detail(user, contract):
            return False

        if getattr(user, "is_superuser", False):
            return True

        if cls.is_manager(user):
            return not getattr(contract, "is_locked", False)

        return (
            cls.is_sales(user)
            and getattr(contract, "created_by_id", None) == getattr(user, "id", None)
            and not getattr(contract, "is_locked", False)
        )

    @classmethod
    def can_delete(cls, user, contract):
        """
        Legacy compatibility.
        """
        return cls.can_delete_contract(user, contract)

    @classmethod
    def can_submit_approval(cls, user, contract=None):
        """
        Hàm mới: nộp duyệt.
        """
        if not cls.is_authenticated_actor(user):
            return False

        if getattr(user, "is_superuser", False):
            return True

        if cls.is_manager(user):
            return True

        if cls.is_sales(user):
            if contract is None:
                return True
            return getattr(contract, "created_by_id", None) == getattr(user, "id", None)

        return False

    @classmethod
    def can_approve_contract(cls, user, contract):
        """
        Hàm mới: duyệt hợp đồng.
        """
        if not cls.is_manager(user):
            return False

        return not getattr(contract, "is_approved", False) and not getattr(contract, "is_locked", False)

    @classmethod
    def can_approve(cls, user, contract):
        """
        Legacy compatibility.
        """
        return cls.can_approve_contract(user, contract)

    # ------------------------------------------------------------------
    # Implementation plan
    # ------------------------------------------------------------------
    @classmethod
    def can_view_implementation(cls, user):
        return cls.is_authenticated_actor(user)

    @classmethod
    def can_edit_implementation(cls, user, contract):
        """
        Chỉ sale tạo kế hoạch / hợp đồng hoặc superuser được sửa nội dung.
        """
        if not cls.is_authenticated_actor(user):
            return False

        if getattr(user, "is_superuser", False):
            return True

        return (
            cls.is_sales(user)
            and getattr(contract, "created_by_id", None) == getattr(user, "id", None)
        )

    @classmethod
    def can_manage_implementation_unlock(cls, user, contract):
        """
        Sale tạo kế hoạch, Executive và superuser được gỡ xác nhận / mở khóa.
        """
        if not cls.is_authenticated_actor(user):
            return False

        if getattr(user, "is_superuser", False):
            return True

        if cls.is_executive(user):
            return True

        return (
            cls.is_sales(user)
            and getattr(contract, "created_by_id", None) == getattr(user, "id", None)
        )

    @classmethod
    def can_view_implementation_logs(cls, user, contract):
        """
        Sale tạo kế hoạch, Executive và superuser được xem toàn bộ log.
        """
        if not cls.is_authenticated_actor(user):
            return False

        if getattr(user, "is_superuser", False):
            return True

        if cls.is_executive(user):
            return True

        return getattr(contract, "created_by_id", None) == getattr(user, "id", None)

    @classmethod
    def can_view_implementation_contract_link(cls, user, contract):
        """
        Link quay về hợp đồng từ trang triển khai.
        """
        if not cls.is_authenticated_actor(user):
            return False

        if getattr(user, "is_superuser", False):
            return True

        if cls.is_executive(user):
            return True

        return getattr(contract, "created_by_id", None) == getattr(user, "id", None)

    # ------------------------------------------------------------------
    # Extra helpers cho code mới / view khác nếu cần
    # ------------------------------------------------------------------
    @classmethod
    def can_view_payment_area(cls, user):
        return cls.is_authenticated_actor(user) and (
            getattr(user, "is_superuser", False)
            or cls.is_manager(user)
            or cls.is_accountant(user)
        )

    @classmethod
    def can_view_operational_area(cls, user):
        return cls.is_authenticated_actor(user) and (
            getattr(user, "is_superuser", False)
            or cls.is_manager(user)
            or cls.is_operations(user)
            or cls.is_nurse(user)
            or cls.is_doctor(user)
        )

    @classmethod
    def can_view_admin_reports(cls, user):
        return cls.is_authenticated_actor(user) and (
            getattr(user, "is_superuser", False)
            or cls.is_manager(user)
            or cls.is_executive(user)
        )
