import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render

from apps.clinical.policies import ClinicalPolicy
from apps.clinical.selectors.dental_selectors import (
    build_dental_exam_page_context,
    build_dental_result_payload,
)
from apps.clinical.services.dental_commands import save_dental_examination
from apps.patients.models import Patient


@login_required(login_url="authentication:staff_login")
def dental_exam_form(request):
    if not ClinicalPolicy.can_manage_dental(request.user):
        return render(
            request,
            "core/403.html",
            {"error_message": "Bạn không có quyền truy cập."},
            status=403,
        )

    context = build_dental_exam_page_context(actor=request.user)
    return render(request, "clinic/staff/dental_exam.html", context)


@login_required(login_url="authentication:staff_login")
def api_save_dental_exam(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Phương thức không hợp lệ."}, status=405)

    if not ClinicalPolicy.can_manage_dental(request.user):
        return JsonResponse({"status": "error", "message": "Không có quyền truy cập."}, status=403)

    try:
        payload = json.loads(request.body.decode("utf-8"))
        patient_id = payload.get("patient_id")
        if not patient_id:
            return JsonResponse({"status": "error", "message": "Thiếu patient_id."}, status=400)

        exam = save_dental_examination(patient_id=patient_id, payload=payload)
        return JsonResponse(
            {
                "status": "success",
                "message": "Lưu khám răng thành công.",
                "data": {
                    "id": exam.id,
                    "patient_id": exam.patient_id,
                },
            }
        )
    except Patient.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Không tìm thấy bệnh nhân."}, status=404)
    except Exception as exc:
        return JsonResponse({"status": "error", "message": str(exc)}, status=400)


@login_required(login_url="authentication:staff_login")
def get_dental_data(request, patient_id):
    if not ClinicalPolicy.can_manage_dental(request.user):
        return JsonResponse({"status": "error", "message": "Không có quyền truy cập."}, status=403)

    try:
        data = build_dental_result_payload(patient_id=patient_id)
        return JsonResponse({"status": "success", "data": data})
    except Patient.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Không tìm thấy bệnh nhân."}, status=404)
    except Exception as exc:
        return JsonResponse({"status": "error", "message": str(exc)}, status=400)