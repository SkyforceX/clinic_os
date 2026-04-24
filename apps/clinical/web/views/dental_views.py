from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from apps.clinical.models import DentalExamination
from apps.clinical.policies import ClinicalPolicy
from apps.clinical.selectors.dental_selectors import (
    build_dental_exam_page_context,
    build_dental_result_payload,
    get_exam_history_for_patient,
)
from apps.clinical.services.dental_commands import save_dental_examination
from apps.his_integration.selectors import (
    list_active_his_patients,
    list_active_his_patients_for_organization,
)


def _can_access_his_patient_list(user):
    return (
        ClinicalPolicy.can_manage_dental(user)
        or ClinicalPolicy.can_manage_pathology(user)
    )


def _extract_tooth_data_from_post(data):
    tooth_data = {}
    for key, value in data.items():
        if not value or not str(value).strip():
            continue
        if key.startswith("tooth_upper_"):
            tooth_no = key.replace("tooth_upper_", "").strip()
            if tooth_no:
                tooth_data[tooth_no] = str(value).strip()
        elif key.startswith("tooth_lower_"):
            tooth_no = key.replace("tooth_lower_", "").strip()
            if tooth_no:
                tooth_data[tooth_no] = str(value).strip()
    return tooth_data


def _build_payload_from_post(request):
    data = request.POST
    return {
        "patient_id":     (data.get("patient_id") or "").strip(),
        "company_id":     (data.get("company_id") or "").strip(),
        "dental_exam_id": (data.get("dental_exam_id") or "").strip(),
        "full_name":      (data.get("full_name") or "").strip(),
        "dob":            (data.get("dob") or "").strip(),
        "gender":         (data.get("gender") or "").strip(),
        "patient_code":   (data.get("patient_code") or "").strip(),
        "additional_notes":          data.get("additional_notes", ""),
        "tooth_loss_classification": data.get("missing_type", ""),
        "other_oral_conditions":     data.get("other_oral_conditions", ""),
        "chewing_ability":           data.get("chewing_ability", ""),
        "health_classification":     data.get("health_classification", ""),
        "conclusion":                data.get("conclusion", ""),
        "tooth_data":                _extract_tooth_data_from_post(data),
    }


# ── AJAX: danh sách BN HIS ────────────────────────────────────────

@login_required(login_url="authentication:staff_login")
def get_his_all_patients(request):
    """AJAX: trả về tất cả HisPatientSync (tối đa 1000)."""
    if not _can_access_his_patient_list(request.user):
        return JsonResponse({"status": "error", "message": "Không có quyền truy cập."}, status=403)

    patients = (
        list_active_his_patients()
        .only("id", "his_patient_code", "full_name", "birth_date_text", "birth_year", "gender_code")
        [:1000]
    )

    data = [
        {
            "id": p.id,
            "ma_bn": p.his_patient_code,
            "ho_ten": p.full_name,
            "gioi_tinh": p.gioi_tinh,
            "ngay_sinh": p.birth_date_display,
            "company_id": "",
        }
        for p in patients
    ]
    return JsonResponse({"patients": data})


@login_required(login_url="authentication:staff_login")
def get_his_patients_by_company(request, company_id):
    """AJAX: trả về HisPatientSync thuộc công ty (qua exam records → package → organization)."""
    if not _can_access_his_patient_list(request.user):
        return JsonResponse({"status": "error", "message": "Không có quyền truy cập."}, status=403)

    patients = (
        list_active_his_patients_for_organization(organization_id=company_id)
        .only("id", "his_patient_code", "full_name", "birth_date_text", "birth_year", "gender_code")
    )

    data = [
        {
            "id": p.id,
            "ma_bn": p.his_patient_code,
            "ho_ten": p.full_name,
            "gioi_tinh": p.gioi_tinh,
            "ngay_sinh": p.birth_date_display,
            "company_id": company_id,
        }
        for p in patients
    ]
    return JsonResponse({"patients": data})


# ── Form khám răng ────────────────────────────────────────────────

@login_required(login_url="authentication:staff_login")
def dental_exam_form(request):
    if not ClinicalPolicy.can_manage_dental(request.user):
        return render(
            request,
            "core/403.html",
            {"error_message": "Bạn không có quyền truy cập."},
            status=403,
        )

    if request.method == "POST":
        payload = _build_payload_from_post(request)
        his_patient_id = payload.get("patient_id") or None  # patient_id field giờ chứa HIS id

        if not his_patient_id and not payload.get("full_name"):
            messages.error(request, "Vui lòng chọn bệnh nhân từ danh sách hoặc nhập họ tên (khách lẻ).")
            return redirect(reverse("clinical:dental_exam_form"))

        try:
            exam = save_dental_examination(
                his_patient_id=int(his_patient_id) if his_patient_id else None,
                payload=payload,
            )
            snapshot = exam.patient_snapshot or {}
            patient_name = (
                exam.his_patient.full_name if exam.his_patient
                else snapshot.get("ho_ten") or (exam.patient.ho_ten if exam.patient else "Khách lẻ")
            )
            messages.success(request, f"Đã lưu phiếu khám thành công — BN: {patient_name}.")
            return redirect(f"{reverse('clinical:dental_exam_form')}?exam_id={exam.id}")

        except ValueError as exc:
            messages.error(request, str(exc))
        except Exception as exc:
            messages.error(request, f"Lỗi khi lưu: {exc}")

        return redirect(reverse("clinical:dental_exam_form"))

    # ── GET ───────────────────────────────────────────────────
    context = build_dental_exam_page_context(actor=request.user)
    context["already_saved"] = False
    context["prefill"] = None

    exam_id = request.GET.get("exam_id")
    if exam_id:
        try:
            prefill = build_dental_result_payload(exam_id=int(exam_id))
            context["prefill"] = prefill
            context["already_saved"] = True
        except (DentalExamination.DoesNotExist, ValueError):
            messages.warning(request, "Không tìm thấy phiếu khám.")

    return render(request, "clinical/staff/dental_exam.html", context)


@login_required(login_url="authentication:staff_login")
def get_dental_data(request, patient_id):
    """AJAX: autofill form khi chọn BN HIS từ sidebar. patient_id = HisPatientSync.id."""
    if not ClinicalPolicy.can_manage_dental(request.user):
        return JsonResponse({"status": "error", "message": "Không có quyền truy cập."}, status=403)
    try:
        data = build_dental_result_payload(patient_id=patient_id)
        return JsonResponse({"status": "success", "data": data})
    except ValueError as exc:
        return JsonResponse({"status": "error", "message": str(exc)}, status=404)
    except Exception as exc:
        return JsonResponse({"status": "error", "message": str(exc)}, status=400)


@login_required(login_url="authentication:staff_login")
def dental_exam_history(request, patient_id):
    """AJAX: danh sách lịch sử khám. patient_id = HisPatientSync.id."""
    if not ClinicalPolicy.can_manage_dental(request.user):
        return JsonResponse({"status": "error", "message": "Không có quyền truy cập."}, status=403)
    try:
        data = get_exam_history_for_patient(patient_id=patient_id)
        return JsonResponse({"status": "success", "data": data})
    except ValueError as exc:
        return JsonResponse({"status": "error", "message": str(exc)}, status=404)
    except Exception as exc:
        return JsonResponse({"status": "error", "message": str(exc)}, status=400)
