import os

from apps.clinical.models import PathologyResult
from apps.his_integration.selectors import get_active_his_patient_by_id
from apps.organizations.selectors.company_selectors import list_companies_for_actor


def build_pathology_page_context(*, actor):
    return {
        "companies": list_companies_for_actor(actor),
    }


def build_pathology_detail_context(*, actor):
    return {
        "companies": list_companies_for_actor(actor),
    }


def build_pathology_results_payload(*, patient_id):
    patient = get_active_his_patient_by_id(patient_id=patient_id)
    if not patient:
        raise ValueError("Không tìm thấy bệnh nhân HIS trong hệ thống.")

    pathology_results = (
        PathologyResult.objects
        .filter(his_patient=patient)
        .order_by("-result_date", "-id")
    )

    result_list = []
    for result in pathology_results:
        file_path = result.file_url.path if result.file_url else ""
        file_exists = bool(file_path) and os.path.exists(file_path)
        result_list.append(
            {
                "id": result.id,
                "location": result.location,
                "result_date": result.result_date.strftime("%d/%m/%Y") if result.result_date else "",
                "file_url": result.file_url.url if result.file_url and file_exists else "",
                "file_exists": file_exists,
                "auto_extracted_text": result.auto_extracted_conclusion or "",
                "manual_conclusion": result.manual_conclusion or "",
                "evaluation": result.evaluation or "",
            }
        )

    return {
        "patient_id": patient.id,
        "patient_code": patient.his_patient_code,
        "full_name": patient.full_name,
        "dob": patient.birth_date_display,
        "gender": patient.gioi_tinh,
        "results": result_list,
    }
