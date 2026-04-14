from dataclasses import dataclass

from django.db import transaction
from django.db.models.deletion import ProtectedError

from apps.organizations.models import Company
from apps.organizations.policies import OrganizationPolicy
from apps.organizations.selectors.company_selectors import company_name_exists


class OrganizationServiceError(Exception):
    pass


class OrganizationPermissionDenied(OrganizationServiceError):
    pass


class OrganizationValidationError(OrganizationServiceError):
    pass


@dataclass(frozen=True)
class CompanyPayload:
    name: str
    address: str = ""
    tax_code: str = ""
    phone: str = ""


def _normalize_text(value):
    return (value or "").strip()


def _validate_payload(payload: CompanyPayload, *, exclude_id=None):
    name = _normalize_text(payload.name)
    if not name:
        raise OrganizationValidationError("Tên công ty là bắt buộc.")

    if company_name_exists(name=name, exclude_id=exclude_id):
        raise OrganizationValidationError("Công ty đã tồn tại.")

    return CompanyPayload(
        name=name,
        address=_normalize_text(payload.address),
        tax_code=_normalize_text(payload.tax_code),
        phone=_normalize_text(payload.phone),
    )


@transaction.atomic
def create_company(*, actor, payload: CompanyPayload):
    if not OrganizationPolicy.can_create(actor):
        raise OrganizationPermissionDenied("Bạn không có quyền tạo công ty.")

    payload = _validate_payload(payload)

    company = Company.objects.create(
        name=payload.name,
        address=payload.address or None,
        tax_code=payload.tax_code or None,
        phone=payload.phone or None,
        created_by=actor,
    )
    return company


@transaction.atomic
def update_company(*, actor, company, payload: CompanyPayload):
    if not OrganizationPolicy.can_update_company(actor, company):
        raise OrganizationPermissionDenied("Bạn không có quyền sửa công ty này.")

    payload = _validate_payload(payload, exclude_id=company.id)

    legacy_company = Company.objects.select_for_update().get(pk=company.id)
    legacy_company.name = payload.name
    legacy_company.address = payload.address or None
    legacy_company.tax_code = payload.tax_code or None
    legacy_company.phone = payload.phone or None
    legacy_company.save(
        update_fields=[
            "name",
            "address",
            "tax_code",
            "phone",
            "updated_at",
        ]
    )
    return legacy_company


@transaction.atomic
def delete_company(*, actor, company):
    if not OrganizationPolicy.can_delete_company(actor, company):
        raise OrganizationPermissionDenied("Bạn không có quyền xóa công ty này.")

    legacy_company = Company.objects.select_for_update().get(pk=company.id)

    try:
        legacy_company.delete()
    except ProtectedError:
        raise OrganizationValidationError(
            "Không thể xóa công ty vì vẫn còn dữ liệu liên kết."
        )
    
    
@transaction.atomic
def upsert_company_from_quotation(
    *,
    actor,
    name: str,
    address: str = "",
    phone: str = "",
    company=None,
):
    if not OrganizationPolicy.can_create(actor):
        raise OrganizationPermissionDenied("Bạn không có quyền tạo/cập nhật công ty.")

    clean_name = _normalize_text(name)
    clean_address = _normalize_text(address)
    clean_phone = _normalize_text(phone)

    if not clean_name:
        raise OrganizationValidationError("Tên công ty là bắt buộc.")

    # Nếu đang sửa một báo giá đã có company gắn sẵn thì cập nhật đúng record đó.
    target = company if getattr(company, "pk", None) else None

    # Nếu là báo giá mới -> luôn tạo company mới,
    # kể cả trùng tên với company của năm trước hoặc cùng năm.
    if target is None:
        return Company.objects.create(
            name=clean_name,
            address=clean_address or None,
            phone=clean_phone or None,
            created_by=actor,
        )

    target.name = clean_name
    target.address = clean_address or None
    if clean_phone:
        target.phone = clean_phone
    if not target.created_by_id:
        target.created_by = actor

    target.save(
        update_fields=[
            "name",
            "address",
            "phone",
            "created_by",
            "updated_at",
        ]
    )
    return target