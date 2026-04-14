import os
from datetime import datetime

from django.conf import settings
from django.db import connection, transaction
from django.shortcuts import get_object_or_404

from apps.clinical.models import PathologyResult
from apps.clinical.services.pathology_ocr import extract_text_from_image_pdf
from apps.patients.models import Patient


SERVER2_UPLOAD_URL = getattr(settings, "PATHOLOGY_SERVER2_UPLOAD_URL", "http://172.39.39.106/api/upload/")
SERVER2_EXISTS_URL = getattr(settings, "PATHOLOGY_SERVER2_EXISTS_URL", "http://172.39.39.106/api/file_exists/")


def _insert_pathology_result(*, patient, location, result_date, manual_conclusion, file_field_name):
    with connection.cursor() as cursor:
        table = PathologyResult._meta.db_table
        cursor.execute(
            f"""
            INSERT INTO {table}
            (
                patient_id,
                location,
                file_url,
                result_date,
                auto_extracted_conclusion,
                manual_conclusion,
                evaluation,
                created_at,
                updated_at
            )
            VALUES
            (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            RETURNING id
            """,
            [
                patient.id,
                location,
                file_field_name,
                result_date,
                "",
                manual_conclusion,
                None,
            ],
        )
        row = cursor.fetchone()
        return row[0]


@transaction.atomic
def save_pathology_result(*, patient_id, uploaded_file, location, result_date, manual_conclusion):
    import requests

    patient = get_object_or_404(Patient, id=patient_id)

    if isinstance(result_date, str):
        result_date = datetime.strptime(result_date, "%Y-%m-%d").date()

    folder_name = result_date.strftime("%m-%Y")
    local_temp_path = os.path.join(settings.MEDIA_ROOT, "temps", folder_name)
    os.makedirs(local_temp_path, exist_ok=True)

    original_name = uploaded_file.name
    temp_file_path = os.path.join(local_temp_path, original_name)

    with open(temp_file_path, "wb+") as destination:
        for chunk in uploaded_file.chunks():
            destination.write(chunk)

    with open(temp_file_path, "rb") as file_handler:
        response = requests.post(
            SERVER2_UPLOAD_URL,
            files={"file": (original_name, file_handler)},
            data={"folder": folder_name},
            timeout=30,
        )
        response.raise_for_status()
        file_path_on_server = response.json().get("file_path", "")

    check_response = requests.get(
        SERVER2_EXISTS_URL,
        params={"path": file_path_on_server},
        timeout=15,
    )
    check_response.raise_for_status()
    if not check_response.json().get("exists", False):
        raise ValueError("File không được lưu thực sự trên Server 2.")

    staging = PathologyResult(
        patient=patient,
        location=location,
        result_date=result_date,
    )
    relative_field_name = staging.file_url.field.generate_filename(staging, original_name)

    created_id = _insert_pathology_result(
        patient=patient,
        location=location,
        result_date=result_date,
        manual_conclusion=manual_conclusion,
        file_field_name=relative_field_name,
    )

    result = PathologyResult.objects.get(id=created_id)
    with open(temp_file_path, "rb") as saved_file:
        result.file_url.save(relative_field_name, saved_file, save=True)

    extracted_text = extract_text_from_image_pdf(result.file_url.path)
    result.auto_extracted_conclusion = extracted_text
    result.save(update_fields=["auto_extracted_conclusion", "updated_at"])

    return result


def update_pathology_evaluation_value(*, result_id, evaluation):
    result = PathologyResult.objects.get(id=result_id)
    result.evaluation = evaluation
    result.save(update_fields=["evaluation", "updated_at"])
    return result