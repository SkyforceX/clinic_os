from dataclasses import dataclass

import pandas as pd
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from apps.organizations.selectors.company_selectors import get_company_for_actor
from apps.patients.policies import PatientPolicy
from apps.patients.services.patient_commands import import_patient_row


EXPECTED_HEADERS = ["mã bn", "họ tên", "giới tính", "ngày sinh", "sđt"]


def normalize_str(value):
    return str(value or "").strip().lower()


def parse_excel_birth_date(value):
    if pd.isna(value):
        return None

    if isinstance(value, str):
        text = value.strip()
        parsed = pd.to_datetime(text, format="%d/%m/%Y", errors="coerce")
        if pd.isna(parsed):
            parsed = pd.to_datetime(text, errors="coerce", dayfirst=True)
        if pd.isna(parsed):
            return None
        return parsed.date()

    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date()


@dataclass(frozen=True)
class ImportPreviewRow:
    row: int
    ma_bn: str
    ho_ten: str
    gioi_tinh: str
    ngay_sinh: object
    phone: str


def extract_patient_rows_from_excel(file):
    df = pd.read_excel(file, header=None)

    actual_headers = [normalize_str(x) for x in df.iloc[1, :5].tolist()]
    if actual_headers != EXPECTED_HEADERS:
        raise ValidationError(f"Tiêu đề không đúng định dạng: {actual_headers}")

    data_start = 2

    empty_index = df[
        df.iloc[:, 0].isna() | (df.iloc[:, 0].astype(str).str.strip() == "")
    ].index.min()

    if pd.isna(empty_index):
        data_end = len(df)
    else:
        data_end = empty_index

    data_df = df.iloc[data_start:data_end, :5]
    data_df = data_df.dropna(how="all")
    data_df = data_df[~(data_df[[0, 1, 2, 3]].isnull().all(axis=1))]

    rows = []
    for idx, row in data_df.iterrows():
        rows.append(
            ImportPreviewRow(
                row=idx + data_start + 1,
                ma_bn=str(row[0]).strip() if pd.notna(row[0]) else "",
                ho_ten=str(row[1]).strip() if pd.notna(row[1]) else "",
                gioi_tinh=str(row[2]).strip() if pd.notna(row[2]) else "",
                ngay_sinh=row[3],
                phone=str(row[4]).strip() if pd.notna(row[4]) else "",
            )
        )
    return rows


@login_required(login_url="authentication:staff_login")
@require_POST
def upload_list_patient(request):
    if request.headers.get("x-requested-with") != "XMLHttpRequest":
        return JsonResponse({"success": False, "error": "Yêu cầu không hợp lệ (phải là AJAX)."})

    if not PatientPolicy.can_import_patients(request.user):
        return JsonResponse({"success": False, "error": "Bạn không có quyền import bệnh nhân."}, status=403)

    force_update = request.POST.get("force_update") == "1"

    try:
        file = request.FILES.get("excel_file")
        company_id = request.POST.get("company_id")

        if not file or not company_id:
            return JsonResponse({"success": False, "error": "Thiếu file hoặc công ty."})

        company = get_company_for_actor(user=request.user, company_id=company_id)
        if not company:
            return JsonResponse({"success": False, "error": "Bạn không có quyền truy cập công ty này."}, status=403)

        rows = extract_patient_rows_from_excel(file)

        error_rows = []
        conflicts = []
        stats = {"created": 0, "updated": 0, "overwritten": 0}

        with transaction.atomic():
            for row in rows:
                missing_fields = []
                if not row.ma_bn:
                    missing_fields.append("Mã BN")
                if not row.ho_ten:
                    missing_fields.append("Họ tên")
                if not row.gioi_tinh:
                    missing_fields.append("Giới tính")
                if pd.isnull(row.ngay_sinh):
                    missing_fields.append("Ngày sinh")

                if missing_fields:
                    error_rows.append(
                        {
                            "row": row.row,
                            "ma_bn": row.ma_bn or "(trống)",
                            "ho_ten": row.ho_ten or "(trống)",
                            "missing": ", ".join(missing_fields),
                        }
                    )
                    continue

                parsed_birth = parse_excel_birth_date(row.ngay_sinh)
                if not parsed_birth:
                    error_rows.append(
                        {
                            "row": row.row,
                            "ma_bn": row.ma_bn,
                            "ho_ten": row.ho_ten,
                            "missing": "Ngày sinh (sai định dạng)",
                        }
                    )
                    continue

                status, conflict_info = import_patient_row(
                    ma_bn=row.ma_bn,
                    ho_ten=row.ho_ten,
                    gioi_tinh=row.gioi_tinh,
                    ngay_sinh=parsed_birth,
                    company=company,
                    phone=row.phone,
                    force_update=force_update,
                )

                if status == "conflict":
                    if conflict_info:
                        conflict_info["row"] = row.row
                        conflicts.append(conflict_info)
                elif status == "created":
                    stats["created"] += 1
                elif status == "updated":
                    stats["updated"] += 1
                elif status == "overwritten":
                    stats["overwritten"] += 1

            if conflicts and not force_update:
                first = conflicts[0]["ma_bn"]
                details = [
                    (
                        f"Dòng {c.get('row', '?')} - Mã BN: {c['ma_bn']}\n"
                        f"  Trong hệ thống: {c['db']}\n"
                        f"  File upload: {c['upload']}\n"
                    )
                    for c in conflicts
                ]
                raise ValidationError(
                    {
                        "error": f"Phát hiện {len(conflicts)} ({first}) mã BN đã tồn tại nhưng thông tin khác.",
                        "details": details,
                    }
                )

        message = "Import thành công."
        if force_update:
            message += (
                f" (created={stats['created']}, updated={stats['updated']}, "
                f"overwritten={stats['overwritten']})"
            )
        else:
            message += f" (created={stats['created']}, updated={stats['updated']})"

        response = {
            "success": True,
            "message": message,
            "stats": stats,
        }
        if error_rows:
            response["warning_rows"] = error_rows

        return JsonResponse(response)

    except ValidationError as exc:
        payload = exc.message_dict if hasattr(exc, "message_dict") else {"error": str(exc)}
        return JsonResponse({"success": False, **payload})

    except Exception as exc:
        return JsonResponse({"success": False, "error": f"Lỗi xử lý: {str(exc)}"})