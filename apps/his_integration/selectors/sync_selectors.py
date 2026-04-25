from __future__ import annotations

from datetime import date

from django.db.models import Count, Prefetch, Q
from django.utils import timezone

from apps.his_integration.models import (
    HisCorporatePackageSync,
    HisExamRecordSync,
    HisPatientSync,
    HisPatientTypeSync,
    HisSyncJob,
)


def find_his_patient_for_login(*, patient_code: str) -> HisPatientSync | None:
    return HisPatientSync.objects.filter(
        his_patient_code=(patient_code or "").strip().upper(),
        is_active=True,
    ).first()


def get_active_his_patient_by_id(*, patient_id) -> HisPatientSync | None:
    return HisPatientSync.objects.filter(
        id=patient_id,
        is_active=True,
    ).first()


def list_active_his_patients():
    return HisPatientSync.objects.filter(is_active=True).order_by("full_name")


def search_active_his_patients(
    *,
    query: str = "",
    name_query: str = "",
    code_query: str = "",
    organization_id=None,
    limit: int = 50,
):
    qs = HisPatientSync.objects.filter(is_active=True)

    if organization_id:
        qs = qs.filter(
            exam_records__package_sync__organization_id=organization_id,
            exam_records__is_active=True,
        ).distinct()

    normalized_name_query = (name_query or "").strip()
    normalized_code_query = (code_query or "").strip()
    normalized_query = (query or "").strip()

    if normalized_name_query:
        name_filter = Q(full_name__icontains=normalized_name_query)
        for token in normalized_name_query.split():
            name_filter &= Q(full_name__icontains=token)
        qs = qs.filter(name_filter)

    if normalized_code_query:
        code_filter = Q(his_patient_code__icontains=normalized_code_query)
        for token in normalized_code_query.split():
            code_filter &= Q(his_patient_code__icontains=token)
        qs = qs.filter(code_filter)
    elif normalized_query:
        name_filter = Q(full_name__icontains=normalized_query)
        for token in normalized_query.split():
            name_filter &= Q(full_name__icontains=token)

        search_filter = name_filter | Q(
            his_patient_code__icontains=normalized_query
        ) | Q(
            phone__icontains=normalized_query
        ) | Q(
            national_id__icontains=normalized_query
        )

        qs = qs.filter(search_filter)

    return qs.order_by("full_name", "his_patient_code")[:limit]


def list_active_his_patients_for_organization(*, organization_id):
    return (
        HisPatientSync.objects
        .filter(
            exam_records__package_sync__organization_id=organization_id,
            exam_records__is_active=True,
            is_active=True,
        )
        .distinct()
        .order_by("full_name")
    )


def count_active_his_patients_for_organization(*, organization_id) -> int:
    return list_active_his_patients_for_organization(
        organization_id=organization_id,
    ).count()


def _parse_his_birth_date(his_patient: HisPatientSync) -> date | None:
    """
    Ghép birth_date_text (NgayThang = DD/MM) + birth_year thành date.
    Hỗ trợ các trường hợp HIS trả dữ liệu khác nhau.
    """
    from datetime import datetime

    birth_text = (his_patient.birth_date_text or "").strip()
    birth_year = his_patient.birth_year

    # Trường hợp birth_date_text chứa đủ ngày/tháng/năm
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(birth_text, fmt).date()
        except (ValueError, AttributeError):
            continue

    # Trường hợp birth_date_text chỉ có DD/MM, ghép với birth_year
    if birth_year and birth_text:
        for fmt in ("%d/%m", "%d-%m"):
            try:
                partial = datetime.strptime(birth_text, fmt)
                return partial.replace(year=birth_year).date()
            except (ValueError, AttributeError):
                continue

    return None


def get_his_patient_birth_date(his_patient: HisPatientSync) -> date | None:
    return _parse_his_birth_date(his_patient)


def verify_his_patient_birth_date(his_patient: HisPatientSync, dob: date) -> bool:
    his_date = _parse_his_birth_date(his_patient)
    if his_date:
        return his_date == dob
    # Fallback: chỉ khớp năm sinh nếu không đủ thông tin DD/MM
    if his_patient.birth_year:
        return dob.year == his_patient.birth_year
    return False


def list_active_schedule_configs_for_his_patient(*, patient_code: str):
    from apps.scheduling.models import ContractScheduleConfig

    code = (patient_code or "").strip().upper()
    if not code:
        return ContractScheduleConfig.objects.none()

    return (
        ContractScheduleConfig.objects.filter(
            his_package__isnull=False,
            his_package__is_active=True,
            his_package__exam_records__is_active=True,
            his_package__exam_records__patient_sync__his_patient_code__iexact=code,
            his_package__exam_records__patient_sync__is_active=True,
        )
        .select_related(
            "quotation",
            "quotation__company",
            "contract",
            "contract__contract",
            "his_package",
            "his_package__organization",
        )
        .distinct()
    )


def get_latest_schedule_config_for_his_patient(*, patient_code: str):
    today = timezone.localdate()
    configs = list_active_schedule_configs_for_his_patient(patient_code=patient_code)
    current = configs.filter(exam_end_date__gte=today).order_by("exam_start_date", "id").first()
    if current:
        return current
    return configs.order_by("-exam_end_date", "-id").first()


def has_active_his_package_for_current_year(*, patient_code: str) -> bool:
    today = timezone.localdate()
    current_year = today.year
    return (
        HisExamRecordSync.objects.filter(
            patient_sync__his_patient_code=(patient_code or "").strip().upper(),
            patient_sync__is_active=True,
            is_active=True,
            package_sync__isnull=False,
            package_sync__is_active=True,
        )
        .filter(
            Q(package_sync__exam_year=current_year)
            | Q(package_sync__exam_year__isnull=True, package_sync__valid_to__gte=today)
        )
        .exists()
    )


def get_his_sync_dashboard_stats() -> dict[str, int]:
    return {
        "patients": HisPatientSync.objects.filter(is_active=True).count(),
        "packages": HisCorporatePackageSync.objects.filter(is_active=True).count(),
        "exam_records": HisExamRecordSync.objects.filter(is_active=True).count(),
        "patient_types": HisPatientTypeSync.objects.filter(is_active=True).count(),
    }


def list_sync_jobs():
    return HisSyncJob.objects.all()


def list_recent_sync_jobs(*, limit: int = 10):
    return list_sync_jobs()[:limit]


def get_patient_sync_by_his_code(*, his_patient_code: str):
    return HisPatientSync.objects.filter(
        his_patient_code=(his_patient_code or "").strip(),
    ).first()


def get_patient_type_sync_by_his_code(*, his_patient_type_code: str):
    return HisPatientTypeSync.objects.filter(
        his_patient_type_code=(his_patient_type_code or "").strip(),
    ).first()


def get_corporate_package_sync_by_his_code(*, his_package_code: str):
    return (
        corporate_package_detail_queryset()
        .filter(his_package_code=(his_package_code or "").strip())
        .first()
    )


def get_active_corporate_package_by_id(*, package_id):
    return corporate_package_detail_queryset().filter(pk=package_id, is_active=True).first()


def _schedule_config_queryset_for_package_linking():
    from apps.scheduling.models import ContractScheduleConfig

    return ContractScheduleConfig.objects.select_related(
        "quotation",
        "quotation__company",
        "contract",
        "contract__contract",
        "his_package",
    )


def get_exam_record_sync_by_his_code(*, his_record_code: str):
    return (
        exam_record_detail_queryset()
        .filter(his_record_code=(his_record_code or "").strip())
        .first()
    )


def list_active_corporate_packages():
    return (
        HisCorporatePackageSync.objects.filter(is_active=True)
        .select_related("contract", "organization")
        .prefetch_related(
            Prefetch(
                "schedule_configs",
                queryset=_schedule_config_queryset_for_package_linking().order_by(
                    "-exam_start_date",
                    "-id",
                ),
            )
        )
        .annotate(
            exam_count=Count("exam_records__patient_sync", distinct=True),
            completed_count=Count(
                "exam_records__patient_sync",
                filter=Q(exam_records__is_complete=True),
                distinct=True,
            ),
        )
        .order_by("-valid_from")
    )


def list_active_corporate_packages_for_sale_user(*, user):
    """Chỉ trả về gói khám được liên kết với lịch khám do user này tạo báo giá."""
    return list_active_corporate_packages().filter(
        schedule_configs__quotation__created_by=user
    ).distinct()


def corporate_package_detail_queryset():
    return HisCorporatePackageSync.objects.select_related("contract", "organization")


def list_exam_records_for_package(*, package):
    return (
        HisExamRecordSync.objects.filter(package_sync=package, is_active=True)
        .select_related("patient_sync", "patient_type_sync")
        .order_by("-exam_date")
    )


def get_package_exam_record_stats(*, package) -> dict[str, int]:
    records = list_exam_records_for_package(package=package)
    total = records.values("patient_sync_id").distinct().count()
    completed = records.filter(is_complete=True).values("patient_sync_id").distinct().count()
    return {
        "total": total,
        "completed": completed,
        "pending": total - completed,
    }


def list_active_exam_records(*, package_id=None, is_complete: bool | None = None):
    qs = (
        HisExamRecordSync.objects.filter(is_active=True)
        .select_related("patient_sync", "package_sync", "patient_type_sync")
        .order_by("-exam_date")
    )

    if package_id:
        qs = qs.filter(package_sync_id=package_id)

    if is_complete is not None:
        qs = qs.filter(is_complete=is_complete)

    return qs


def list_active_packages_for_filter():
    return HisCorporatePackageSync.objects.filter(is_active=True).order_by("package_name")


def list_contracts_available_for_his_package_link(*, package=None):
    from apps.contract.models import Contract
    from apps.contract.models.contract import ACTIVE_STATUSES

    qs = (
        Contract.objects
        .select_related("company")
        .filter(status__in=ACTIVE_STATUSES)
        .order_by("-approved_at", "-created_at", "-id")
    )

    if package and package.contract_id:
        return qs.filter(Q(his_packages__isnull=True) | Q(his_packages=package)).distinct()

    return qs.filter(his_packages__isnull=True)


def get_contract_available_for_his_package_link(*, package, contract_id):
    return (
        list_contracts_available_for_his_package_link(package=package)
        .filter(pk=contract_id)
        .first()
    )


def list_schedule_configs_available_for_his_package_link(*, package=None):
    qs = _schedule_config_queryset_for_package_linking().order_by("-exam_start_date", "-id")

    if package:
        return qs.filter(Q(his_package__isnull=True) | Q(his_package=package)).distinct()

    return qs.filter(his_package__isnull=True)


def get_schedule_config_available_for_his_package_link(*, package, schedule_config_id):
    return (
        list_schedule_configs_available_for_his_package_link(package=package)
        .filter(pk=schedule_config_id)
        .first()
    )


def exam_record_detail_queryset():
    return HisExamRecordSync.objects.select_related(
        "patient_sync",
        "package_sync",
        "patient_type_sync",
    )
