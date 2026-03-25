from datetime import date

from django.contrib.postgres.aggregates import ArrayAgg
from django.db.models import DateField, F, Q, Subquery, Value
from django.db.models.functions import Coalesce, JSONObject

from apps.booking.models import BloodCollectionInfo, HealthContract
from apps.organizations.selectors.company_selectors import (
    get_company_for_actor,
    list_companies_for_actor,
)
from apps.patients.models import Patient


def patient_base_queryset():
    return Patient.objects.select_related("company").all()


def list_patients_for_actor(user):
    company_ids = list(list_companies_for_actor(user).values_list("id", flat=True))
    return patient_base_queryset().filter(company_id__in=company_ids).order_by("id")


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
        contract = HealthContract.objects.get(id=contract_id)
    except HealthContract.DoesNotExist:
        return None, "Không tìm thấy hợp đồng."

    contract_end = (
        getattr(contract, "end_date", None)
        or (contract.created_at.date() if getattr(contract, "created_at", None) else None)
        or date.today()
    )

    min_blood_date_sq = Subquery(
        BloodCollectionInfo.objects
        .filter(contract_id=contract_id)
        .order_by("collection_date")
        .values("collection_date")[:1]
    )

    min_blood_date_sq = Coalesce(
        min_blood_date_sq,
        Value(
            contract.created_at.date() if getattr(contract, "created_at", None) else date.today(),
            output_field=DateField(),
        ),
    )

    patients = (
        Patient.objects
        .filter(company_id=company_id)
        .annotate(
            blood_docs=ArrayAgg(
                JSONObject(
                    id=F("documents__id"),
                    file=F("documents__file"),
                    visit_date=F("documents__visit_date"),
                    is_final=F("documents__is_final"),
                    created_at=F("documents__created_at"),
                ),
                filter=(
                    Q(documents__company_id=company_id)
                    & Q(documents__visit_date__gte=min_blood_date_sq)
                    & Q(documents__visit_date__lte=Value(contract_end))
                ),
                ordering=[F("documents__visit_date").desc()],
            ),
            imaging_docs=ArrayAgg(
                JSONObject(
                    id=F("documents__id"),
                    file=F("documents__file"),
                    visit_date=F("documents__visit_date"),
                    is_final=F("documents__is_final"),
                    created_at=F("documents__created_at"),
                ),
                filter=(
                    Q(documents__company_id=company_id)
                    & Q(documents__visit_date__gte=min_blood_date_sq)
                    & Q(documents__visit_date__lte=Value(contract_end))
                ),
                ordering=[F("documents__visit_date").desc()],
            ),
            periodic_book_docs=ArrayAgg(
                JSONObject(
                    id=F("documents__id"),
                    file=F("documents__file"),
                    visit_date=F("documents__visit_date"),
                    is_final=F("documents__is_final"),
                    created_at=F("documents__created_at"),
                ),
                filter=(
                    Q(documents__company_id=company_id)
                    & Q(documents__visit_date__gte=min_blood_date_sq)
                    & Q(documents__visit_date__lte=Value(contract_end))
                ),
                ordering=[F("documents__visit_date").desc()],
            ),
        )
        .values(
            "id",
            "uuid",
            "ma_bn",
            "ho_ten",
            "gioi_tinh",
            "ngay_sinh",
            "phone",
            "blood_docs",
            "imaging_docs",
            "periodic_book_docs",
        )
        .order_by("id")
    )

    return {
        "contract_end": contract_end,
        "rows": list(patients),
    }, None