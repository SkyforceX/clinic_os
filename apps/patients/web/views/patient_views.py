from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from apps.organizations.selectors.company_selectors import get_company_for_actor
from apps.patients.models import Patient
from apps.patients.policies import PatientPolicy
from apps.patients.selectors.patient_selectors import (
    get_patient_for_actor,
    list_patients_by_company_for_actor,
    list_patients_for_actor,
)
from apps.patients.services.patient_commands import (
    PatientPayload,
    PatientPermissionDenied,
    PatientValidationError,
    delete_patient_record,
    update_patient_record,
)


@login_required(login_url="authentication:staff_login")
def get_patients_by_company(request, company_id):
    patients = list_patients_by_company_for_actor(user=request.user, company_id=company_id)
    data = [
        {
            "id": p.id,
            "ma_bn": p.ma_bn,
            "ho_ten": p.ho_ten,
            "gioi_tinh": p.gioi_tinh,
            "ngay_sinh": p.ngay_sinh.strftime("%Y-%m-%d") if p.ngay_sinh else "",
        }
        for p in patients
    ]
    return JsonResponse({"patients": data})


@login_required(login_url="authentication:staff_login")
def get_all_patients(request):
    patients = list_patients_for_actor(request.user)
    data = [
        {
            "id": p.id,
            "ho_ten": p.ho_ten,
            "ma_bn": p.ma_bn,
            "gioi_tinh": p.gioi_tinh,
            "ngay_sinh": p.ngay_sinh.strftime("%d/%m/%Y") if p.ngay_sinh else "",
        }
        for p in patients
    ]
    return JsonResponse({"patients": data})


@login_required(login_url="authentication:staff_login")
@require_POST
def update_patient_ajax(request, patient_id):
    patient = get_patient_for_actor(user=request.user, patient_id=patient_id)
    if not patient:
        return JsonResponse(
            {
                "success": False,
                "message": "Không tìm thấy bệnh nhân.",
            },
            status=404,
        )

    if not PatientPolicy.can_update_patient(request.user):
        return JsonResponse(
            {
                "success": False,
                "message": "Bạn không có quyền thực hiện thao tác này.",
            },
            status=403,
        )

    try:
        updated = update_patient_record(
            actor=request.user,
            patient=patient,
            payload=PatientPayload(
                ma_bn=request.POST.get("ma_bn"),
                ho_ten=request.POST.get("ho_ten"),
                gioi_tinh=request.POST.get("gioi_tinh"),
                ngay_sinh=request.POST.get("ngay_sinh"),
                phone=request.POST.get("phone"),
            ),
        )

        return JsonResponse(
            {
                "success": True,
                "message": "Cập nhật bệnh nhân thành công.",
                "patient": {
                    "id": updated.id,
                    "ma_bn": updated.ma_bn,
                    "ho_ten": updated.ho_ten,
                    "gioi_tinh": updated.gioi_tinh,
                    "ngay_sinh": updated.ngay_sinh.strftime("%d/%m/%Y"),
                    "ngay_sinh_iso": updated.ngay_sinh.strftime("%Y-%m-%d"),
                    "phone": updated.phone or "",
                },
            }
        )

    except PatientValidationError as exc:
        errors = exc.args[0] if exc.args else {"__all__": "Dữ liệu chưa hợp lệ."}
        return JsonResponse(
            {
                "success": False,
                "message": "Dữ liệu chưa hợp lệ.",
                "errors": errors if isinstance(errors, dict) else {"__all__": str(errors)},
            },
            status=400,
        )

    except PatientPermissionDenied as exc:
        return JsonResponse(
            {
                "success": False,
                "message": str(exc),
            },
            status=403,
        )

    except Exception as exc:
        return JsonResponse(
            {
                "success": False,
                "message": str(exc),
            },
            status=500,
        )


@login_required(login_url="authentication:staff_login")
@require_POST
def delete_patient_ajax(request, patient_id):
    patient = get_patient_for_actor(user=request.user, patient_id=patient_id)
    if not patient:
        return JsonResponse(
            {
                "success": False,
                "message": "Không tìm thấy bệnh nhân.",
            },
            status=404,
        )

    try:
        patient_name = patient.ho_ten
        delete_patient_record(actor=request.user, patient=patient)
        return JsonResponse(
            {
                "success": True,
                "message": f"Đã xóa bệnh nhân '{patient_name}'.",
                "patient_id": patient_id,
            }
        )

    except PatientPermissionDenied as exc:
        return JsonResponse(
            {
                "success": False,
                "message": str(exc),
            },
            status=403,
        )

    except Exception as exc:
        return JsonResponse(
            {
                "success": False,
                "message": str(exc),
            },
            status=500,
        )

@login_required(login_url="authentication:staff_login")
@require_POST
def delete_patients_by_company(request, company_id):
    """
    Xóa toàn bộ nhân viên/BN thuộc một công ty.
    Chỉ dành cho Managers có quyền xóa (theo PatientPolicy.can_delete_patient).
    """
    if not PatientPolicy.can_delete_patient(request.user):
        return JsonResponse(
            {
                "success": False,
                "message": "Bạn không có quyền thực hiện thao tác này.",
            },
            status=403,
        )

    company = get_company_for_actor(user=request.user, company_id=company_id)
    if not company:
        return JsonResponse(
            {
                "success": False,
                "message": "Không tìm thấy công ty hoặc bạn không có quyền truy cập.",
            },
            status=404,
        )

    try:
        deleted_count, _ = Patient.objects.filter(company_id=company.id).delete()
        return JsonResponse(
            {
                "success": True,
                "message": f"Đã xóa {deleted_count} nhân viên khỏi công ty '{company.name}'.",
                "deleted_count": deleted_count,
            }
        )

    except Exception as exc:
        return JsonResponse(
            {
                "success": False,
                "message": f"Lỗi khi xóa: {exc}",
            },
            status=500,
        )