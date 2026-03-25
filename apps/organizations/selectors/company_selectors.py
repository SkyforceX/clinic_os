from django.db.models import Count

from apps.organizations.models import Company
from apps.organizations.policies import OrganizationPolicy


def company_base_queryset():
    return Company.objects.select_related("created_by").all()


def list_companies_for_actor(user):
    qs = company_base_queryset()

    if OrganizationPolicy.is_manager(user):
        return qs.order_by("-id")

    return qs.filter(created_by=user).order_by("-id")


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