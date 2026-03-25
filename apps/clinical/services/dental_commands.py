from decimal import Decimal, InvalidOperation

from django.db import connection, transaction

from apps.clinical.models import DentalExamination
from apps.organizations.models import Company
from apps.patients.models import Patient


def _normalize_decimal(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return Decimal(raw)
    except (InvalidOperation, ValueError):
        return None


@transaction.atomic
def save_dental_examination(*, patient_id, payload):
    patient = Patient.objects.select_related("company").get(id=patient_id)
    company = patient.company or Company.objects.filter(id=payload.get("company_id")).first()
    if not company:
        raise ValueError("Không tìm thấy công ty của bệnh nhân.")

    tooth_data = payload.get("tooth_data") or {}
    additional_notes = payload.get("additional_notes", "")
    tooth_loss_classification = payload.get("tooth_loss_classification", "")
    other_oral_conditions = payload.get("other_oral_conditions", "")
    chewing_ability = _normalize_decimal(payload.get("chewing_ability"))
    health_classification = payload.get("health_classification", "")
    conclusion = payload.get("conclusion", "")

    existing = (
        DentalExamination.objects
        .filter(patient=patient)
        .order_by("-updated_at", "-id")
        .first()
    )

    if existing:
        existing.company = company
        existing.additional_notes = additional_notes
        existing.tooth_data = tooth_data
        existing.tooth_loss_classification = tooth_loss_classification
        existing.other_oral_conditions = other_oral_conditions
        existing.chewing_ability = chewing_ability
        existing.health_classification = health_classification
        existing.conclusion = conclusion
        existing.save(
            update_fields=[
                "company",
                "additional_notes",
                "tooth_data",
                "tooth_loss_classification",
                "other_oral_conditions",
                "chewing_ability",
                "health_classification",
                "conclusion",
                "updated_at",
            ]
        )
        return existing

    with connection.cursor() as cursor:
        table = DentalExamination._meta.db_table
        cursor.execute(
            f"""
            INSERT INTO {table}
            (
                patient_id,
                company_id,
                additional_notes,
                tooth_data,
                tooth_loss_classification,
                other_oral_conditions,
                chewing_ability,
                health_classification,
                conclusion,
                created_at,
                updated_at
            )
            VALUES
            (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            RETURNING id
            """,
            [
                patient.id,
                company.id,
                additional_notes,
                tooth_data,
                tooth_loss_classification,
                other_oral_conditions,
                chewing_ability,
                health_classification,
                conclusion,
            ],
        )
        row = cursor.fetchone()
        created_id = row[0]

    return DentalExamination.objects.get(id=created_id)