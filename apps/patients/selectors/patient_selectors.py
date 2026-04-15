from datetime import date

from django.db.models import Q

from apps.contract.models import Contract
from apps.organizations.selectors.company_selectors import (
    get_company_for_actor,
    list_companies_for_actor,
)
from apps.patients.models.patients import Patient


def patient_base_queryset():
    return Patient.objects.select_related("company").all()


def list_patients_for_actor(user):
    """
    Trả về toàn bộ bệnh nhân mà actor có thể thấy:
    - Bệnh nhân thuộc các công ty actor được phép
    - Bệnh nhân lẻ (company=None) — luôn hiển thị để hỗ trợ khám lẻ
    """
    company_ids = list(list_companies_for_actor(user).values_list("id", flat=True))
    return (
        patient_base_queryset()
        .filter(Q(company__isnull=True) | Q(company_id__in=company_ids))
        .order_by("id")
    )


def list_patients_by_company_for_actor(*, user, company_id):
    company = get_company_for_actor(user=user, company_id=company_id)
    if not company:
        return Patient.objects.none()
    return patient_base_queryset().filter(company_id=company.id).order_by("id")


def get_patient_for_actor(*, user, patient_id):
    return list_patients_for_actor(user).filter(id=patient_id).first()


def get_patient_by_code(ma_bn):
    return patient_base_queryset().filter(ma_bn=(ma_bn or "").strip()).first()


def patient_code_exists(*, ma_bn, exclude_id=None):
    qs = Patient.objects.filter(ma_bn=(ma_bn or "").strip())
    if exclude_id:
        qs = qs.exclude(id=exclude_id)
    return qs.exists()


def get_company_scoped_for_actor(*, user, company_id):
    return get_company_for_actor(user=user, company_id=company_id)


def build_patient_documents_payload(*, company_id, contract_id):
    try:
        contract = Contract.objects.get(id=contract_id)
    except Contract.DoesNotExist:
        return None, "Không tìm thấy hợp đồng."

    contract_end = (
        getattr(contract, "end_date", None)
        or (contract.created_at.date() if getattr(contract, "created_at", None) else None)
        or date.today()
    )

    patients = list(
        Patient.objects.filter(company_id=company_id)
        .values("id", "uuid", "ma_bn", "ho_ten", "gioi_tinh", "ngay_sinh", "phone")
        .order_by("id")
    )

    for row in patients:
        row["blood_docs"] = []
        row["imaging_docs"] = []
        row["periodic_book_docs"] = []

    return {
        "contract_end": contract_end,
        "rows": patients,
    }, None
