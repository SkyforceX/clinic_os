import pytest
from django.core.management import call_command

from apps.procedures.models import Procedure, ProcedureStep
from apps.procedures.services.procedure_seed_services import SEEDED_PROCEDURE_CODES
from apps.procedures.services.procedure_services import create_procedure, create_step


@pytest.mark.django_db
@pytest.mark.smoke
def test_can_create_procedure_and_nested_steps(superuser):
    procedure = create_procedure(
        {
            "title": "Quy trinh test",
            "code": "QT-TEST-001",
            "category": "operations",
            "description": "Mo ta test",
            "status": "draft",
            "version": "1.0",
            "effective_date": "",
        },
        superuser,
    )

    parent = create_step(
        procedure,
        {
            "title": "Buoc 1",
            "description": "Mo ta buoc 1",
            "responsible": "QA",
            "duration": "5 phut",
            "color": "#0d6efd",
        },
    )
    child = create_step(
        procedure,
        {
            "title": "Buoc 1.1",
            "description": "Mo ta buoc con",
            "responsible": "QA",
            "duration": "2 phut",
            "color": "#198754",
            "parent_id": parent.pk,
        },
    )

    assert Procedure.objects.filter(pk=procedure.pk).exists()
    assert ProcedureStep.objects.filter(pk=parent.pk, procedure=procedure).exists()
    assert child.parent_id == parent.pk


@pytest.mark.django_db
@pytest.mark.smoke
def test_seed_clinic_os_usage_procedures_command_creates_seeded_records(superuser):
    call_command(
        "seed_clinic_os_usage_procedures",
        creator_username=superuser.username,
        verbosity=0,
    )

    seeded = Procedure.objects.filter(code__in=SEEDED_PROCEDURE_CODES)
    assert seeded.count() == len(SEEDED_PROCEDURE_CODES)
    assert ProcedureStep.objects.filter(procedure__code="QT-CLINICOS-001").exists()
