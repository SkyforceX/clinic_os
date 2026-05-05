from __future__ import annotations

from datetime import date, timedelta

from django.db.models import Count
from django.utils import timezone

from apps.ai_knowledge.services.permissions import can_access_clinical_context
from apps.booking.models import Appointment
from apps.contract.models import ACTIVE_STATUSES, Contract
from apps.contract.models.quotation import QuotationDraft
from apps.contract.policies import ContractPolicy
from apps.hrm.selectors.employee_selectors import list_employees
from apps.organizations.selectors.company_selectors import list_companies_for_actor
from apps.patients.models.patients import Patient
from apps.reception.models import CheckInRecord
from apps.record_completion.models import OVERDUE_DAYS, RecordCompletion


def _today():
    return timezone.localdate()


def count_employees_for_user(user) -> int | None:
    if not getattr(user, "is_authenticated", False):
        return None
    return list_employees().count()


def _normalize_company_name(value: str) -> str:
    return (value or "").strip()


def _quotations_for_user(user):
    if not getattr(user, "is_authenticated", False):
        return None

    queryset = QuotationDraft.objects.filter(company__isnull=False)
    if getattr(user, "is_superuser", False) or ContractPolicy.is_manager(user) or ContractPolicy.is_executive(user):
        return queryset

    if ContractPolicy.is_sales(user):
        return queryset.filter(created_by=user)

    return None


def count_quotations_for_user(
    user,
    *,
    status: str | None = None,
    created_today: bool = False,
    target_date: date | None = None,
    company_name: str | None = None,
) -> int | None:
    queryset = _quotations_for_user(user)
    if queryset is None:
        return None
    if status:
        queryset = queryset.filter(status=status)
    if target_date:
        queryset = queryset.filter(created_at__date=target_date)
    elif created_today:
        queryset = queryset.filter(created_at__date=_today())
    if company_name:
        query_name = _normalize_company_name(company_name)
        queryset = queryset.filter(company__name__icontains=query_name)
    return queryset.count()


def list_quotation_summaries_for_user(
    user,
    *,
    status: str | None = None,
    created_today: bool = False,
    target_date: date | None = None,
    company_name: str | None = None,
    limit: int = 5,
) -> list[dict] | None:
    queryset = _quotations_for_user(user)
    if queryset is None:
        return None
    if status:
        queryset = queryset.filter(status=status)
    if target_date:
        queryset = queryset.filter(created_at__date=target_date)
    elif created_today:
        queryset = queryset.filter(created_at__date=_today())
    if company_name:
        query_name = _normalize_company_name(company_name)
        queryset = queryset.filter(company__name__icontains=query_name)
    rows = queryset.select_related("company").order_by("-created_at", "-id")[:limit]
    return [
        {
            "id": row.id,
            "company_name": row.company_name or getattr(row.company, "name", "") or "Không xác định",
            "status": row.status,
            "valid_until": row.valid_until,
        }
        for row in rows
    ]


def list_top_quotation_companies_for_user(
    user,
    *,
    status: str | None = None,
    created_today: bool = False,
    target_date: date | None = None,
    limit: int = 5,
) -> list[dict] | None:
    queryset = _quotations_for_user(user)
    if queryset is None:
        return None
    if status:
        queryset = queryset.filter(status=status)
    if target_date:
        queryset = queryset.filter(created_at__date=target_date)
    elif created_today:
        queryset = queryset.filter(created_at__date=_today())
    rows = (
        queryset.values("company__name")
        .annotate(total=Count("id"))
        .order_by("-total", "company__name")[:limit]
    )
    return [
        {"company_name": row["company__name"] or "Không xác định", "total": row["total"]}
        for row in rows
    ]


def _contracts_for_user(user):
    if not getattr(user, "is_authenticated", False):
        return None

    queryset = Contract.objects.all()
    if getattr(user, "is_superuser", False) or ContractPolicy.is_manager(user) or ContractPolicy.is_executive(user):
        return queryset

    if ContractPolicy.is_sales(user):
        return queryset.filter(created_by=user)

    return None


def count_contracts_for_user(
    user,
    *,
    status: str | None = None,
    created_today: bool = False,
    target_date: date | None = None,
    active_only: bool = False,
    company_name: str | None = None,
) -> int | None:
    queryset = _contracts_for_user(user)
    if queryset is None:
        return None
    if active_only:
        queryset = queryset.filter(status__in=ACTIVE_STATUSES)
    if status:
        queryset = queryset.filter(status=status)
    if target_date:
        queryset = queryset.filter(created_at__date=target_date)
    elif created_today:
        queryset = queryset.filter(created_at__date=_today())
    if company_name:
        query_name = _normalize_company_name(company_name)
        queryset = queryset.filter(company__name__icontains=query_name)
    return queryset.count()


def list_contract_summaries_for_user(
    user,
    *,
    status: str | None = None,
    created_today: bool = False,
    target_date: date | None = None,
    active_only: bool = False,
    company_name: str | None = None,
    limit: int = 5,
) -> list[dict] | None:
    queryset = _contracts_for_user(user)
    if queryset is None:
        return None
    if active_only:
        queryset = queryset.filter(status__in=ACTIVE_STATUSES)
    if status:
        queryset = queryset.filter(status=status)
    if target_date:
        queryset = queryset.filter(created_at__date=target_date)
    elif created_today:
        queryset = queryset.filter(created_at__date=_today())
    if company_name:
        query_name = _normalize_company_name(company_name)
        queryset = queryset.filter(company__name__icontains=query_name)
    rows = queryset.select_related("company").order_by("-created_at", "-id")[:limit]
    return [
        {
            "id": row.id,
            "company_name": getattr(row.company, "name", "") or "Không xác định",
            "contract_number": row.contract_number or f"HĐ#{row.id}",
            "status": row.status,
            "end_date": row.end_date,
        }
        for row in rows
    ]


def list_top_contract_companies_for_user(
    user,
    *,
    status: str | None = None,
    created_today: bool = False,
    target_date: date | None = None,
    active_only: bool = False,
    limit: int = 5,
) -> list[dict] | None:
    queryset = _contracts_for_user(user)
    if queryset is None:
        return None
    if active_only:
        queryset = queryset.filter(status__in=ACTIVE_STATUSES)
    if status:
        queryset = queryset.filter(status=status)
    if target_date:
        queryset = queryset.filter(created_at__date=target_date)
    elif created_today:
        queryset = queryset.filter(created_at__date=_today())
    rows = (
        queryset.values("company__name")
        .annotate(total=Count("id"))
        .order_by("-total", "company__name")[:limit]
    )
    return [
        {"company_name": row["company__name"] or "Không xác định", "total": row["total"]}
        for row in rows
    ]


def count_companies_for_user(user) -> int | None:
    if not getattr(user, "is_authenticated", False):
        return None
    return list_companies_for_actor(user).count()


def count_patients_for_user(user) -> int | None:
    if not getattr(user, "is_authenticated", False):
        return None
    if not (getattr(user, "is_superuser", False) or can_access_clinical_context(user)):
        return None
    return Patient.objects.count()


def count_appointments_for_user(
    user,
    *,
    status: str | None = None,
    today_only: bool = False,
    target_date: date | None = None,
) -> int | None:
    if not getattr(user, "is_authenticated", False):
        return None
    queryset = Appointment.objects.all()
    if status:
        queryset = queryset.filter(status=status)
    if target_date:
        queryset = queryset.filter(schedule_slot__date=target_date)
    elif today_only:
        queryset = queryset.filter(schedule_slot__date=_today())
    return queryset.count()


def list_appointment_summaries_for_user(
    user,
    *,
    status: str | None = None,
    today_only: bool = False,
    target_date: date | None = None,
    limit: int = 5,
) -> list[dict] | None:
    if not getattr(user, "is_authenticated", False):
        return None
    queryset = Appointment.objects.select_related(
        "patient",
        "his_patient_sync",
        "schedule_slot",
    )
    if status:
        queryset = queryset.filter(status=status)
    if target_date:
        queryset = queryset.filter(schedule_slot__date=target_date)
    elif today_only:
        queryset = queryset.filter(schedule_slot__date=_today())
    rows = queryset.order_by("-booked_at", "-id")[:limit]
    return [
        {
            "id": row.id,
            "patient_name": (
                getattr(row.his_patient_sync, "full_name", None)
                or getattr(row.patient, "ho_ten", None)
                or "Không xác định"
            ),
            "status": row.status,
            "date": getattr(row.schedule_slot, "date", None),
        }
        for row in rows
    ]


def count_checkins_for_user(
    user,
    *,
    status: str | None = None,
    today_only: bool = False,
    target_date: date | None = None,
    company_name: str | None = None,
) -> int | None:
    if not getattr(user, "is_authenticated", False):
        return None
    queryset = CheckInRecord.objects.all()
    if status:
        queryset = queryset.filter(status=status)
    if target_date:
        queryset = queryset.filter(exam_date=target_date)
    elif today_only:
        queryset = queryset.filter(exam_date=_today())
    if company_name:
        query_name = _normalize_company_name(company_name)
        queryset = queryset.filter(snapshot_company_name__icontains=query_name)
    return queryset.count()


def list_checkin_summaries_for_user(
    user,
    *,
    status: str | None = None,
    today_only: bool = False,
    target_date: date | None = None,
    company_name: str | None = None,
    limit: int = 5,
) -> list[dict] | None:
    if not getattr(user, "is_authenticated", False):
        return None
    queryset = CheckInRecord.objects.all()
    if status:
        queryset = queryset.filter(status=status)
    if target_date:
        queryset = queryset.filter(exam_date=target_date)
    elif today_only:
        queryset = queryset.filter(exam_date=_today())
    if company_name:
        query_name = _normalize_company_name(company_name)
        queryset = queryset.filter(snapshot_company_name__icontains=query_name)
    rows = queryset.order_by("-exam_date", "-checked_in_at", "-id")[:limit]
    return [
        {
            "id": row.id,
            "patient_code": row.snapshot_ma_bn,
            "patient_name": row.snapshot_ho_ten,
            "company_name": row.snapshot_company_name or "Không xác định",
            "status": row.status,
            "exam_date": row.exam_date,
        }
        for row in rows
    ]


def list_top_checkin_companies_for_user(
    user,
    *,
    status: str | None = None,
    today_only: bool = False,
    target_date: date | None = None,
    limit: int = 5,
) -> list[dict] | None:
    if not getattr(user, "is_authenticated", False):
        return None
    queryset = CheckInRecord.objects.all()
    if status:
        queryset = queryset.filter(status=status)
    if target_date:
        queryset = queryset.filter(exam_date=target_date)
    elif today_only:
        queryset = queryset.filter(exam_date=_today())
    rows = (
        queryset.values("snapshot_company_name")
        .annotate(total=Count("id"))
        .order_by("-total", "snapshot_company_name")[:limit]
    )
    return [
        {"company_name": row["snapshot_company_name"] or "Không xác định", "total": row["total"]}
        for row in rows
    ]


def list_overdue_record_completion_summaries_for_user(
    user,
    *,
    company_name: str | None = None,
    limit: int = 5,
) -> list[dict] | None:
    if not getattr(user, "is_authenticated", False):
        return None
    overdue_threshold = _today() - timedelta(days=OVERDUE_DAYS)
    queryset = RecordCompletion.objects.select_related("checkin_record", "company").filter(
        is_completed=False,
        checkin_record__exam_date__lt=overdue_threshold,
    )
    if company_name:
        query_name = _normalize_company_name(company_name)
        queryset = queryset.filter(checkin_record__snapshot_company_name__icontains=query_name)
    rows = queryset.order_by("checkin_record__exam_date", "checkin_record__snapshot_ho_ten")[:limit]
    return [
        {
            "id": row.id,
            "patient_code": row.checkin_record.snapshot_ma_bn,
            "patient_name": row.checkin_record.snapshot_ho_ten,
            "company_name": row.checkin_record.snapshot_company_name or "Không xác định",
            "exam_date": row.checkin_record.exam_date,
            "current_step": row.current_step,
            "days_overdue": max(0, (_today() - row.checkin_record.exam_date).days - OVERDUE_DAYS),
        }
        for row in rows
    ]
