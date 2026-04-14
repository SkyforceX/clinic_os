import os

from apps.clinical.models import PathologyResult
from apps.organizations.selectors.company_selectors import list_companies_for_actor
from apps.patients.models import Patient


def build_pathology_page_context(*, actor):
    return {
        "companies": list_companies_for_actor(actor),
    }


def build_pathology_detail_context(*, actor):
    return {
        "companies": list_companies_for_actor(actor),
    }


def build_pathology_results_payload(*, patient_id):
    patient = Patient.objects.get(id=patient_id)
    pathology_results = PathologyResult.objects.filter(patient=patient).order_by("-result_date", "-id")

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
        "patient_code": patient.ma_bn,
        "full_name": patient.ho_ten,
        "dob": patient.ngay_sinh.strftime("%d-%m-%Y") if patient.ngay_sinh else "",
        "gender": patient.gioi_tinh,
        "results": result_list,
    }