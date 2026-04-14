from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from apps.patients.selectors.patient_selectors import (
    build_patient_documents_payload,
    get_company_scoped_for_actor,
)
from apps.patients.services.import_patients import upload_list_patient
from apps.patients.services.patient_commands import (
    PatientPayload,
    PatientPermissionDenied,
    PatientValidationError,
    create_patient_for_company,
)


def _normalize_docs(doc_list):
    if not doc_list:
        return []

    rows = []
    for doc in doc_list:
        if not doc:
            continue

        visit_date = doc.get("visit_date")
        if visit_date:
            visit_date = visit_date if isinstance(visit_date, str) else visit_date.strftime("%d/%m/%Y")
        else:
            visit_date = ""

        rows.append(
            {
                "id": doc.get("id"),
                "file": doc.get("file"),
                "visit_date": visit_date,
                "is_final": doc.get("is_final"),
                "created_at": doc.get("created_at"),
            }
        )
    return rows


@login_required(login_url="authentication:staff_login")
def ajax_patient_list_json(request, company_id, contract_id):
    company = get_company_scoped_for_actor(user=request.user, company_id=company_id)
    if not company:
        return JsonResponse({"error": "Bạn không có quyền truy cập công ty này."}, status=403)

    payload, error = build_patient_documents_payload(company_id=company_id, contract_id=contract_id)
    if error:
        return JsonResponse({"error": error}, status=404)

    contract_end = payload["contract_end"]
    rows = payload["rows"]

    data = []
    for row in rows:
        data.append(
            {
                "id": row["id"],
                "uuid": str(row["uuid"]) if row.get("uuid") else "",
                "ma_bn": row["ma_bn"],
                "ho_ten": row["ho_ten"],
                "gioi_tinh": row["gioi_tinh"],
                "phone": row["phone"] or "",
                "ngay_sinh": row["ngay_sinh"].strftime("%d/%m/%Y") if row.get("ngay_sinh") else "",
                "range": {
                    "from_blood": None,
                    "to_contract_end": contract_end.strftime("%d/%m/%Y") if contract_end else "",
                },
                "blood_files": _normalize_docs(row.get("blood_docs")),
                "imaging_files": _normalize_docs(row.get("imaging_docs")),
                "periodic_book_files": _normalize_docs(row.get("periodic_book_docs")),
            }
        )

    return JsonResponse({"patients": data})


@login_required(login_url="authentication:staff_login")
def create_patient_ajax(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Phương thức không hợp lệ."}, status=405)

    try:
        patient, message = create_patient_for_company(
            actor=request.user,
            company_id=request.POST.get("company_id"),
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
                "message": message,
                "patient": {
                    "id": patient.id,
                    "ma_bn": patient.ma_bn,
                    "ho_ten": patient.ho_ten,
                    "gioi_tinh": patient.gioi_tinh,
                    "ngay_sinh": patient.ngay_sinh.strftime("%d/%m/%Y") if patient.ngay_sinh else "",
                    "phone": patient.phone or "",
                    "company_id": patient.company_id,
                },
            }
        )

    except PatientValidationError as exc:
        payload = exc.args[0] if exc.args else "Dữ liệu chưa hợp lệ."
        return JsonResponse(
            {
                "success": False,
                "error": payload if isinstance(payload, str) else "Dữ liệu chưa hợp lệ.",
                "errors": payload if isinstance(payload, dict) else None,
            },
            status=400,
        )

    except PatientPermissionDenied as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=403)

    except Exception as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=500)