from apps.clinical.models import DentalExamination, ToothNotation
from apps.organizations.selectors.company_selectors import list_companies_for_actor
from apps.patients.models import Patient


def build_dental_exam_page_context(*, actor):
    companies = list_companies_for_actor(actor)
    notations = ToothNotation.objects.all().order_by("code")
    notation_map = {item.code: item.description_vi for item in notations}

    return {
        "companies": companies,
        "notations": notations,
        "notation_map": notation_map,
    }


def build_dental_result_payload(*, patient_id):
    patient = Patient.objects.select_related("company").get(id=patient_id)
    dental_exam = (
        DentalExamination.objects.filter(patient=patient).order_by("-updated_at", "-id").first()
    )

    data = {
        "full_name": patient.ho_ten,
        "dob": patient.ngay_sinh.strftime("%d/%m/%Y") if patient.ngay_sinh else "",
        "gender": patient.gioi_tinh,
        "patient_code": patient.ma_bn,
        "loss_classification": dental_exam.tooth_loss_classification if dental_exam else "",
        "other_oral_conditions": dental_exam.other_oral_conditions if dental_exam else "",
        "chewing_ability": str(dental_exam.chewing_ability) if dental_exam and dental_exam.chewing_ability else "",
        "health_classification": dental_exam.health_classification if dental_exam else "",
        "conclusion": dental_exam.conclusion if dental_exam else "",
        "tooth_details": {},
    }

    if dental_exam and dental_exam.tooth_data:
        for tooth, notation_code in dental_exam.tooth_data.items():
            try:
                tooth_num = int(tooth)
            except (TypeError, ValueError):
                continue
            prefix = "tooth_upper" if 11 <= tooth_num <= 28 else "tooth_lower"
            data["tooth_details"][f"{prefix}_{tooth}"] = notation_code

    return data