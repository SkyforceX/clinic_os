from __future__ import annotations

from django.conf import settings

from apps.catalogs.policies import CatalogPolicy
from apps.procedures.policies import can_view_procedures

from apps.ai_knowledge.models import AIKnowledgeSource


CLINICAL_GROUPS = {
    "Doctors",
    "Nurses",
    "Lab Technicians",
    "Imaging Technicians",
    "Quality",
}
CONTRACT_GROUPS = {"Managers", "Manager", "Sales Team", "Executives", "Executive"}
MANAGER_GROUPS = {"Managers", "Manager", "Executives", "Executive"}
AI_ASSISTANT_ALLOWED_GROUPS = getattr(
    settings,
    "AI_ASSISTANT_ALLOWED_GROUPS",
    list(MANAGER_GROUPS | CLINICAL_GROUPS | CONTRACT_GROUPS),
)


def _has_group(user, allowed_names: set[str]) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if not getattr(user, "pk", None):
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=allowed_names).exists()


def _user_can_access_ai(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if not getattr(user, "pk", None):
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=AI_ASSISTANT_ALLOWED_GROUPS).exists()


def can_access_clinical_context(user) -> bool:
    return _has_group(user, CLINICAL_GROUPS)


def can_access_contract_context(user, contract_id=None) -> bool:
    return _has_group(user, CONTRACT_GROUPS)


def can_access_patient_context(user, patient_id=None) -> bool:
    return can_access_clinical_context(user)


def get_allowed_access_levels(user) -> list[str]:
    if not getattr(user, "is_authenticated", False):
        return [AIKnowledgeSource.ACCESS_PUBLIC]

    levels = [AIKnowledgeSource.ACCESS_PUBLIC]
    if _user_can_access_ai(user) or user.is_staff:
        levels.append(AIKnowledgeSource.ACCESS_INTERNAL)
    if _has_group(user, MANAGER_GROUPS):
        levels.append(AIKnowledgeSource.ACCESS_MANAGER)
    if can_access_contract_context(user):
        levels.append(AIKnowledgeSource.ACCESS_CONTRACT)
    if can_access_clinical_context(user):
        levels.extend(
            [
                AIKnowledgeSource.ACCESS_CLINICAL,
                AIKnowledgeSource.ACCESS_PATIENT,
            ]
        )
    if user.is_superuser or _has_group(user, set(AI_ASSISTANT_ALLOWED_GROUPS)):
        levels.append(AIKnowledgeSource.ACCESS_ADMIN)

    deduped: list[str] = []
    for level in levels:
        if level not in deduped:
            deduped.append(level)
    return deduped


def get_allowed_source_types(user) -> list[str]:
    source_types: list[str] = [
        AIKnowledgeSource.SOURCE_SERVICE,
        AIKnowledgeSource.SOURCE_FAQ,
        AIKnowledgeSource.SOURCE_CATEGORY,
        AIKnowledgeSource.SOURCE_PACKAGE,
    ]

    if can_view_procedures(user):
        source_types.append(AIKnowledgeSource.SOURCE_PROCEDURE)
    if CatalogPolicy.can_view_categories(user):
        source_types.append(AIKnowledgeSource.SOURCE_CATEGORY)
    if CatalogPolicy.can_view_packages(user):
        source_types.append(AIKnowledgeSource.SOURCE_PACKAGE)

    if _user_can_access_ai(user) or getattr(user, "is_staff", False):
        source_types.extend(
            [
                AIKnowledgeSource.SOURCE_DOCUMENT,
                AIKnowledgeSource.SOURCE_INTERNAL_NOTE,
                AIKnowledgeSource.SOURCE_POLICY,
            ]
        )

    if can_access_contract_context(user):
        source_types.extend(
            [
                AIKnowledgeSource.SOURCE_CONTRACT,
                AIKnowledgeSource.SOURCE_QUOTATION,
                AIKnowledgeSource.SOURCE_DOCUMENT,
            ]
        )

    if can_access_clinical_context(user):
        source_types.extend(
            [
                AIKnowledgeSource.SOURCE_PATIENT_SUMMARY,
                AIKnowledgeSource.SOURCE_VISIT_SUMMARY,
                AIKnowledgeSource.SOURCE_CLINICAL_NOTE,
                AIKnowledgeSource.SOURCE_MEDICAL_RECORD,
            ]
        )

    deduped: list[str] = []
    for source_type in source_types:
        if source_type not in deduped:
            deduped.append(source_type)
    return deduped
