import json
from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render

from apps.clinical.models import PathologyResult
from apps.clinical.policies import ClinicalPolicy
from apps.clinical.selectors.pathology_selectors import (
    build_pathology_detail_context,
    build_pathology_page_context,
    build_pathology_results_payload,
)
from apps.clinical.services.pathology_commands import (
    save_pathology_result,
    update_pathology_evaluation_value,
)
from apps.patients.models import Patient


@login_required(login_url="authentication:staff_login")
def pathology(request):
    if not ClinicalPolicy.can_manage_pathology(request.user):
        return render(
            request,
            "core/403.html",
            {"error_message": "Bạn không có quyền truy cập."},
            status=403,
        )
    return render(
        request,
        "clinic/staff/pathology.html",
        build_pathology_page_context(actor=request.user),
    )


@login_required(login_url="authentication:staff_login")
def pathology_detail(request):
    if not ClinicalPolicy.can_manage_pathology(request.user):
        return render(
            request,
            "core/403.html",
            {"error_message": "Bạn không có quyền truy cập."},
            status=403,
        )
    return render(
        request,
        "clinic/staff/pathology_detail.html",
        build_pathology_detail_context(actor=request.user),
    )


@login_required(login_url="authentication:staff_login")
def upload_pathology_pdf(request):
    if request.method != "POST":
        return redirect("clinical:pathology")

    if not ClinicalPolicy.can_manage_pathology(request.user):
        messages.error(request, "Bạn không có quyền thực hiện thao tác này.")
        return redirect("clinical:pathology")

    uploaded_file = request.FILES.get("pdf_file")
    patient_id = request.POST.get("patient_id")
    location = request.POST.get("location", "Không xác định")
    result_date = request.POST.get("result_date")
    manual_conclusion = (request.POST.get("manual_conclusion") or "").strip()

    if not uploaded_file:
        messages.error(request, "Thiếu file PDF.")
        return redirect("clinical:pathology")

    try:
        datetime.strptime(result_date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        messages.error(request, "Ngày không hợp lệ.")
        return redirect("clinical:pathology")

    try:
        save_pathology_result(
            patient_id=patient_id,
            uploaded_file=uploaded_file,
            location=location,
            result_date=result_date,
            manual_conclusion=manual_conclusion,
        )
        messages.success(request, "Tải file thành công!")
    except Exception as exc:
        messages.error(request, str(exc))

    return redirect("clinical:pathology")


@login_required(login_url="authentication:staff_login")
def get_pathology_data(request, patient_id):
    if not ClinicalPolicy.can_manage_pathology(request.user):
        return JsonResponse({"status": "error", "message": "Không có quyền truy cập."}, status=403)

    try:
        payload = build_pathology_results_payload(patient_id=patient_id)
        return JsonResponse({"status": "success", "data": payload})
    except Patient.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Không tìm thấy bệnh nhân."}, status=404)
    except Exception as exc:
        return JsonResponse({"status": "error", "message": str(exc)}, status=400)


@login_required(login_url="authentication:staff_login")
def update_pathology_evaluation(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Phương thức không hợp lệ."}, status=405)

    if not ClinicalPolicy.can_manage_pathology(request.user):
        return JsonResponse({"status": "error", "message": "Không có quyền truy cập."}, status=403)

    try:
        payload = json.loads(request.body)
        result = update_pathology_evaluation_value(
            result_id=payload.get("result_id"),
            evaluation=payload.get("evaluation"),
        )
        return JsonResponse(
            {
                "status": "success",
                "data": {
                    "id": result.id,
                    "evaluation": result.evaluation,
                },
            }
        )
    except PathologyResult.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Không tìm thấy kết quả."}, status=404)
    except Exception as exc:
        return JsonResponse({"status": "error", "message": str(exc)}, status=400)