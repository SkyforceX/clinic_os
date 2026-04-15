from dataclasses import dataclass
from datetime import date, datetime

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date

from apps.organizations.selectors.company_selectors import get_company_for_actor
from apps.patients.models.patients import Patient, PatientCompanyHistory
from apps.patients.policies import PatientPolicy
from apps.patients.selectors.patient_selectors import patient_code_exists


class PatientServiceError(Exception):
    pass


class PatientPermissionDenied(PatientServiceError):
    pass


class PatientValidationError(PatientServiceError):
    pass


@dataclass(frozen=True)
class PatientPayload:
    ma_bn: str
    ho_ten: str
    gioi_tinh: str
    ngay_sinh: object
    phone: str = ""


def normalize_str(value):
    return str(value or "").strip().lower()


def normalize_text(value):
    return str(value or "").strip()


def parse_birth_date(value):
    if value is None or value == "":
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    if isinstance(value, str):
        text = value.strip()
        parsed = parse_date(text)
        if parsed:
            return parsed

        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue

    return None


def validate_patient_payload(payload: PatientPayload, *, exclude_id=None):
    ma_bn = normalize_text(payload.ma_bn)
    ho_ten = normalize_text(payload.ho_ten)
    gioi_tinh = normalize_text(payload.gioi_tinh)
    phone = normalize_text(payload.phone)
    ngay_sinh = parse_birth_date(payload.ngay_sinh)

    errors = {}

    if not ma_bn:
        errors["ma_bn"] = "Vui lòng nhập mã bệnh nhân."
    if not ho_ten:
        errors["ho_ten"] = "Vui lòng nhập họ tên."
    if not gioi_tinh:
        errors["gioi_tinh"] = "Vui lòng chọn giới tính."
    if not ngay_sinh:
        errors["ngay_sinh"] = "Ngày sinh không hợp lệ."

    if ma_bn and patient_code_exists(ma_bn=ma_bn, exclude_id=exclude_id):
        errors["ma_bn"] = "Mã bệnh nhân đã tồn tại trong hệ thống."

    if errors:
        raise PatientValidationError(errors)

    return PatientPayload(
        ma_bn=ma_bn,
        ho_ten=ho_ten,
        gioi_tinh=gioi_tinh,
        ngay_sinh=ngay_sinh,
        phone=phone,
    )


@transaction.atomic
def get_or_create_walkin_patient(*, payload: dict) -> Patient:
    """
    Tìm hoặc tạo bệnh nhân lẻ (không thuộc công ty nào).

    - Nếu patient_code đã tồn tại trong DB → trả về bệnh nhân đó.
    - Nếu không có patient_code → tự sinh mã dạng KL<timestamp>.
    - Tạo bản ghi Patient mới với company=None.
    """
    ma_bn    = normalize_text(payload.get("patient_code") or "")
    ho_ten   = normalize_text(payload.get("full_name")    or "")
    dob_str  = normalize_text(payload.get("dob")          or "")
    gioi_tinh = normalize_text(payload.get("gender")      or "")

    if not ho_ten:
        raise PatientValidationError({"ho_ten": "Vui lòng nhập họ tên bệnh nhân."})

    ngay_sinh = parse_birth_date(dob_str)
    if not ngay_sinh:
        raise PatientValidationError(
            {"ngay_sinh": "Ngày sinh không hợp lệ. Vui lòng nhập theo định dạng dd/mm/yyyy."}
        )

    # Tìm bệnh nhân đã có theo mã BN
    if ma_bn:
        existing = Patient.objects.filter(ma_bn=ma_bn).first()
        if existing:
            return existing

    # Tự sinh mã BN dạng KL<YYYYmmddHHMMSS> khi không nhập
    if not ma_bn:
        base = timezone.now().strftime("KL%Y%m%d%H%M%S")
        ma_bn = base
        suffix = 1
        while Patient.objects.filter(ma_bn=ma_bn).exists():
            ma_bn = f"{base}{suffix}"
            suffix += 1

    patient = Patient.objects.create(
        ma_bn=ma_bn,
        ho_ten=ho_ten,
        gioi_tinh=gioi_tinh or "Không rõ",
        ngay_sinh=ngay_sinh,
        company=None,
    )
    return patient


@transaction.atomic
def reassign_patient_company(*, patient, company):
    today = date.today()

    if patient.company_id != company.id:
        PatientCompanyHistory.objects.filter(
            patient=patient,
            to_date__isnull=True,
        ).update(to_date=today)

        PatientCompanyHistory.objects.create(
            patient=patient,
            company=company,
            from_date=today,
        )

        patient.company = company
        patient.save(update_fields=["company", "updated_at"])


@transaction.atomic
def import_patient_row(*, ma_bn, ho_ten, gioi_tinh, ngay_sinh, company, phone=None, force_update=False):
    today = date.today()
    clean_ma_bn = normalize_text(ma_bn)
    clean_ho_ten = normalize_text(ho_ten)
    clean_gioi_tinh = normalize_text(gioi_tinh)
    clean_phone = normalize_text(phone)
    parsed_ngay_sinh = parse_birth_date(ngay_sinh)

    if not parsed_ngay_sinh:
        raise PatientValidationError({"ngay_sinh": "Ngày sinh không hợp lệ."})

    patient = Patient.objects.filter(ma_bn=clean_ma_bn).first()

    if patient:
        is_same = (
            normalize_str(patient.ho_ten) == normalize_str(clean_ho_ten)
            and normalize_str(patient.gioi_tinh) == normalize_str(clean_gioi_tinh)
            and patient.ngay_sinh == parsed_ngay_sinh
        )

        if not is_same:
            if not force_update:
                conflict_info = {
                    "ma_bn": clean_ma_bn,
                    "db": {
                        "ho_ten": patient.ho_ten,
                        "gioi_tinh": patient.gioi_tinh,
                        "ngay_sinh": patient.ngay_sinh.strftime("%d/%m/%Y"),
                    },
                    "upload": {
                        "ho_ten": clean_ho_ten,
                        "gioi_tinh": clean_gioi_tinh,
                        "ngay_sinh": parsed_ngay_sinh.strftime("%d/%m/%Y"),
                    },
                }
                return "conflict", conflict_info

            update_fields = ["ho_ten", "gioi_tinh", "ngay_sinh", "phone", "updated_at"]

            if patient.company_id != company.pk:
                PatientCompanyHistory.objects.filter(
                    patient=patient, to_date__isnull=True
                ).update(to_date=today)
                PatientCompanyHistory.objects.create(
                    patient=patient, company=company, from_date=today
                )
                patient.company_id = company.pk
                update_fields.append("company")

            patient.ho_ten = clean_ho_ten
            patient.gioi_tinh = clean_gioi_tinh
            patient.ngay_sinh = parsed_ngay_sinh
            patient.phone = clean_phone or None
            patient.save(update_fields=list(dict.fromkeys(update_fields)))
            return "overwritten", None

        changed_fields = []

        if patient.company_id != company.pk:
            PatientCompanyHistory.objects.filter(
                patient=patient, to_date__isnull=True
            ).update(to_date=today)
            PatientCompanyHistory.objects.create(
                patient=patient, company=company, from_date=today
            )
            patient.company_id = company.pk
            changed_fields.append("company")

        if normalize_str(patient.ho_ten) != normalize_str(clean_ho_ten):
            patient.ho_ten = clean_ho_ten
            changed_fields.append("ho_ten")

        if normalize_str(patient.gioi_tinh) != normalize_str(clean_gioi_tinh):
            patient.gioi_tinh = clean_gioi_tinh
            changed_fields.append("gioi_tinh")

        if patient.ngay_sinh != parsed_ngay_sinh:
            patient.ngay_sinh = parsed_ngay_sinh
            changed_fields.append("ngay_sinh")

        new_phone = clean_phone or None
        if patient.phone != new_phone:
            patient.phone = new_phone
            changed_fields.append("phone")

        if changed_fields:
            changed_fields.append("updated_at")
            patient.save(update_fields=changed_fields)

        return "updated", None

    patient = Patient.objects.create(
        ma_bn=clean_ma_bn,
        ho_ten=clean_ho_ten,
        gioi_tinh=clean_gioi_tinh,
        ngay_sinh=parsed_ngay_sinh,
        company=company,
        phone=clean_phone or None,
    )

    PatientCompanyHistory.objects.create(
        patient=patient, company=company, from_date=today
    )
    return "created", None


@transaction.atomic
def create_patient_for_company(*, actor, company_id, payload: PatientPayload):
    if not PatientPolicy.can_create_patient(actor):
        raise PatientPermissionDenied("Bạn không có quyền tạo bệnh nhân.")

    company = get_company_for_actor(user=actor, company_id=company_id)
    if not company:
        raise PatientPermissionDenied("Bạn không có quyền truy cập công ty này.")

    payload = PatientPayload(
        ma_bn=normalize_text(payload.ma_bn),
        ho_ten=normalize_text(payload.ho_ten),
        gioi_tinh=normalize_text(payload.gioi_tinh),
        ngay_sinh=parse_birth_date(payload.ngay_sinh),
        phone=normalize_text(payload.phone),
    )

    if not payload.ma_bn or not payload.ho_ten or not payload.gioi_tinh or not payload.ngay_sinh:
        raise PatientValidationError(
            {
                "ma_bn": "Thiếu thông tin bắt buộc." if not payload.ma_bn else "",
                "ho_ten": "Thiếu thông tin bắt buộc." if not payload.ho_ten else "",
                "gioi_tinh": "Thiếu thông tin bắt buộc." if not payload.gioi_tinh else "",
                "ngay_sinh": "Thiếu thông tin bắt buộc." if not payload.ngay_sinh else "",
            }
        )

    patient = Patient.objects.filter(ma_bn=payload.ma_bn).first()

    if patient:
        is_same = (
            normalize_str(patient.ho_ten) == normalize_str(payload.ho_ten)
            and normalize_str(patient.gioi_tinh) == normalize_str(payload.gioi_tinh)
            and patient.ngay_sinh == payload.ngay_sinh
        )

        if is_same:
            if patient.company_id != company.id:
                reassign_patient_company(patient=patient, company=company)
            return patient, "Bệnh nhân đã có trong hệ thống, đã gán lại công ty."

        raise PatientValidationError(
            {"ma_bn": "Mã BN đã tồn tại với thông tin khác. Vui lòng kiểm tra lại!"}
        )

    patient = Patient.objects.create(
        company=company,
        ma_bn=payload.ma_bn,
        ho_ten=payload.ho_ten,
        gioi_tinh=payload.gioi_tinh,
        ngay_sinh=payload.ngay_sinh,
        phone=payload.phone or None,
    )

    PatientCompanyHistory.objects.create(
        patient=patient, company=company, from_date=date.today()
    )
    return patient, "Thêm bệnh nhân thành công!"


@transaction.atomic
def update_patient_record(*, actor, patient, payload: PatientPayload):
    if not PatientPolicy.can_update_patient(actor):
        raise PatientPermissionDenied("Bạn không có quyền thực hiện thao tác này.")

    payload = validate_patient_payload(payload, exclude_id=patient.id)

    legacy_patient = Patient.objects.select_for_update().get(pk=patient.id)
    legacy_patient.ma_bn = payload.ma_bn
    legacy_patient.ho_ten = payload.ho_ten
    legacy_patient.gioi_tinh = payload.gioi_tinh
    legacy_patient.ngay_sinh = payload.ngay_sinh
    legacy_patient.phone = payload.phone or None

    legacy_patient.save(
        update_fields=["ma_bn", "ho_ten", "gioi_tinh", "ngay_sinh", "phone", "updated_at"]
    )
    return legacy_patient


@transaction.atomic
def delete_patient_record(*, actor, patient):
    if not PatientPolicy.can_delete_patient(actor):
        raise PatientPermissionDenied("Bạn không có quyền xóa bệnh nhân.")

    legacy_patient = Patient.objects.select_for_update().get(pk=patient.id)
    legacy_patient.delete()
