from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from celery import chain
from django.core.exceptions import ObjectDoesNotExist

from apps.his_integration import tasks
from apps.his_integration.services.his_source_clients import SOURCE_HIS_MSSQL


SYNC_PATIENT_TYPES = "patient_types"
SYNC_PATIENTS = "patients"
SYNC_PACKAGES = "packages"
SYNC_EXAM_RECORDS = "exam_records"
SYNC_ALL = "all"


class InvalidHisSyncType(ValueError):
    pass


@dataclass(frozen=True)
class HisSyncStep:
    sync_type: str
    label: str
    task: Any
    kwargs: dict[str, Any]


def _get_triggered_by_id(*, actor) -> int | None:
    if not actor:
        return None

    try:
        return actor.employee.id
    except (AttributeError, ObjectDoesNotExist):
        return None


def _build_single_step(
    *,
    sync_type: str,
    reset_cursor: bool,
    patient_batch_size: int,
    exam_batch_size: int,
    triggered_by_id: int | None,
    source: str,
) -> HisSyncStep:
    if sync_type == SYNC_PATIENT_TYPES:
        return HisSyncStep(
            sync_type=sync_type,
            label="patient types",
            task=tasks.sync_patient_types_from_his,
            kwargs={"triggered_by_id": triggered_by_id, "source": source},
        )

    if sync_type == SYNC_PATIENTS:
        return HisSyncStep(
            sync_type=sync_type,
            label="patients",
            task=tasks.sync_patients_from_his,
            kwargs={
                "batch_size": patient_batch_size,
                "reset_cursor": reset_cursor,
                "triggered_by_id": triggered_by_id,
                "source": source,
            },
        )

    if sync_type == SYNC_PACKAGES:
        return HisSyncStep(
            sync_type=sync_type,
            label="corporate packages",
            task=tasks.sync_corporate_packages_from_his,
            kwargs={"triggered_by_id": triggered_by_id, "source": source},
        )

    if sync_type == SYNC_EXAM_RECORDS:
        return HisSyncStep(
            sync_type=sync_type,
            label="exam records",
            task=tasks.sync_exam_records_from_his,
            kwargs={
                "batch_size": exam_batch_size,
                "reset_cursor": reset_cursor,
                "triggered_by_id": triggered_by_id,
                "source": source,
            },
        )

    raise InvalidHisSyncType(sync_type)


def build_his_sync_steps(
    *,
    sync_type: str,
    actor=None,
    triggered_by_id: int | None = None,
    reset_cursor: bool = False,
    patient_batch_size: int = 500,
    exam_batch_size: int = 300,
    source: str = SOURCE_HIS_MSSQL,
) -> tuple[HisSyncStep, ...]:
    if triggered_by_id is None:
        triggered_by_id = _get_triggered_by_id(actor=actor)

    if sync_type == SYNC_ALL:
        sync_types = (
            SYNC_PATIENT_TYPES,
            SYNC_PATIENTS,
            SYNC_PACKAGES,
            SYNC_EXAM_RECORDS,
        )
    else:
        sync_types = (sync_type,)

    return tuple(
        _build_single_step(
            sync_type=item,
            reset_cursor=reset_cursor,
            patient_batch_size=patient_batch_size,
            exam_batch_size=exam_batch_size,
            triggered_by_id=triggered_by_id,
            source=source,
        )
        for item in sync_types
    )


def dispatch_his_sync(
    *,
    sync_type: str,
    actor=None,
    reset_cursor: bool = False,
    patient_batch_size: int = 500,
    exam_batch_size: int = 300,
    source: str = SOURCE_HIS_MSSQL,
    run_inline: bool = False,
) -> dict[str, Any]:
    steps = build_his_sync_steps(
        sync_type=sync_type,
        actor=actor,
        reset_cursor=reset_cursor,
        patient_batch_size=patient_batch_size,
        exam_batch_size=exam_batch_size,
        source=source,
    )

    if run_inline:
        results = []
        for step in steps:
            result = run_his_sync_step_inline(step)
            results.append(result)
            if not result.successful():
                return {
                    "task_id": result.id,
                    "sync_type": sync_type,
                    "source": source,
                    "step_count": len(steps),
                    "inline": True,
                    "success": False,
                    "error": str(result.result),
                }

        return {
            "task_id": results[-1].id if results else None,
            "sync_type": sync_type,
            "source": source,
            "step_count": len(steps),
            "inline": True,
            "success": True,
        }

    if len(steps) == 1:
        async_result = steps[0].task.apply_async(kwargs=steps[0].kwargs)
    else:
        workflow = chain(*(step.task.si(**step.kwargs) for step in steps))
        async_result = workflow.apply_async()

    return {
        "task_id": async_result.id,
        "sync_type": sync_type,
        "source": source,
        "step_count": len(steps),
        "inline": False,
        "success": True,
    }


def run_his_sync_step_inline(step: HisSyncStep):
    return step.task.apply(kwargs=step.kwargs)
