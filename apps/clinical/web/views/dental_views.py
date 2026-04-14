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
from apps.patients.models import Patient
from apps.patients.services.patient_commands import PatientValidationError


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
        # Định danh bệnh nhân — rỗng nếu là khách lẻ nhập tay
        "patient_id":   (data.get("patient_id") or "").strip(),
        "company_id":   (data.get("company_id") or "").strip(),
        "dental_exam_id": (data.get("dental_exam_id") or "").strip(),
        # Thông tin hành chính — dùng để tạo walk-in patient nếu patient_id rỗng
        "full_name":    (data.get("full_name") or "").strip(),
        "dob":          (data.get("dob") or "").strip(),
        "gender":       (data.get("gender") or "").strip(),
        "patient_code": (data.get("patient_code") or "").strip(),
        # Dữ liệu khám lâm sàng
        "additional_notes":       data.get("additional_notes", ""),
        "tooth_loss_classification": data.get("missing_type", ""),
        "other_oral_conditions":  data.get("other_oral_conditions", ""),
        "chewing_ability":        data.get("chewing_ability", ""),
        "health_classification":  data.get("health_classification", ""),
        "conclusion":             data.get("conclusion", ""),
        "tooth_data":             _extract_tooth_data_from_post(data),
    }


@login_required(login_url="authentication:staff_login")
def dental_exam_form(request):
    if not ClinicalPolicy.can_manage_dental(request.user):
        return render(
            request,
            "core/403.html",
            {"error_message": "Bạn không có quyền truy cập."},
            status=403,
        )

    # ── POST: lưu form ────────────────────────────────────────
    if request.method == "POST":
        payload = _build_payload_from_post(request)
        patient_id = payload.get("patient_id") or None  # None nếu rỗng

        # Khách lẻ: bắt buộc có họ tên
        if not patient_id and not payload.get("full_name"):
            messages.error(request, "Vui lòng chọn bệnh nhân từ danh sách hoặc nhập họ tên (khách lẻ).")
            return redirect(reverse("clinical:dental_exam_form"))

        try:
            exam = save_dental_examination(
                patient_id=int(patient_id) if patient_id else None,
                payload=payload,
            )
            messages.success(
                request,
                f"Đã lưu phiếu khám thành công — BN: {exam.patient.ho_ten}.",
            )
            return redirect(f"{reverse('clinical:dental_exam_form')}?exam_id={exam.id}")

        except PatientValidationError as exc:
            err = exc.args[0] if exc.args else "Dữ liệu bệnh nhân chưa hợp lệ."
            if isinstance(err, dict):
                err = "; ".join(v for v in err.values() if v)
            messages.error(request, err)
        except Patient.DoesNotExist:
            messages.error(request, "Không tìm thấy bệnh nhân trong hệ thống.")
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
    """AJAX: autofill form khi chọn bệnh nhân từ sidebar."""
    if not ClinicalPolicy.can_manage_dental(request.user):
        return JsonResponse({"status": "error", "message": "Không có quyền truy cập."}, status=403)
    try:
        data = build_dental_result_payload(patient_id=patient_id)
        return JsonResponse({"status": "success", "data": data})
    except Patient.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Không tìm thấy bệnh nhân."}, status=404)
    except Exception as exc:
        return JsonResponse({"status": "error", "message": str(exc)}, status=400)


@login_required(login_url="authentication:staff_login")
def dental_exam_history(request, patient_id):
    """AJAX: danh sách lịch sử khám cho modal."""
    if not ClinicalPolicy.can_manage_dental(request.user):
        return JsonResponse({"status": "error", "message": "Không có quyền truy cập."}, status=403)
    try:
        data = get_exam_history_for_patient(patient_id=patient_id)
        return JsonResponse({"status": "success", "data": data})
    except Patient.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Không tìm thấy bệnh nhân."}, status=404)
    except Exception as exc:
        return JsonResponse({"status": "error", "message": str(exc)}, status=400)
