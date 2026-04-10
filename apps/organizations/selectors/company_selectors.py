from django.db.models import Count, Q
from django.utils import timezone

from apps.organizations.models import Company
from apps.organizations.policies import OrganizationPolicy


def current_company_visible_year():
    return timezone.localdate().year


def company_base_queryset():
    return Company.objects.select_related("created_by").all()


def list_companies_for_actor(user):
    qs = company_base_queryset()

    if OrganizationPolicy.is_manager(user):
        return qs.order_by("-id")

    visible_year = current_company_visible_year()
    return qs.filter(
        created_by=user,
        created_at__year=visible_year,
    ).order_by("-id")


def list_companies_with_counts_for_actor(user):
    """
    Trả về danh sách công ty kèm:
    - patient_count  : số bệnh nhân thuộc công ty
    - contract_count : số hợp đồng của công ty
      (related_name mặc định Django = 'contract_set' nếu Contract
       không khai báo related_name; đổi thành 'contracts' nếu cần)
    """
    qs = list_companies_for_actor(user)
    return qs.annotate(
        patient_count=Count("patients", distinct=True),
        contract_count=Count("contracts", distinct=True),
    )


def list_companies_with_patient_count_for_actor(user):
    qs = list_companies_for_actor(user)
    return qs.annotate(patient_count=Count("patients"))


def get_company_for_actor(*, user, company_id):
    qs = list_companies_for_actor(user)
    return qs.filter(id=company_id).first()


def company_name_exists(*, name, exclude_id=None):
    qs = Company.objects.filter(name__iexact=(name or "").strip())
    if exclude_id:
        qs = qs.exclude(id=exclude_id)
    return qs.exists()