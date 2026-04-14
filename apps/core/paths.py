# core/paths.py
import os
import unicodedata, re
from datetime import date

def slugify_ascii(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "na"

def build_patient_doc_path(instance, filename: str) -> str:
    """
    results/by-patient/{patient_code}-{patient_uuid}/{YYYY}/{YYYYMMDD}/{doc_type}.pdf
    """
    # Lấy mã BN & UUID từ FK patient
    # ĐỔI 'ma_bn' nếu field mã BN của bạn tên khác (vd: patient_code)
    code = getattr(instance.patient, "ma_bn", None) or getattr(instance.patient, "patient_code", "BN")
    patient_code = slugify_ascii(str(code))
    patient_uuid = str(getattr(instance.patient, "uuid", getattr(instance.patient, "id", "unknown")))

    y = instance.visit_date.year if isinstance(instance.visit_date, date) else int(str(instance.visit_date)[:4])
    ymd = instance.visit_date.strftime("%Y%m%d")
    doc = instance.doc_type  # "paraclinical" | "clinical"
    fname = f"{doc}.pdf"     # tên file cố định → sẽ ghi đè nếu cùng ngày & loại

    return os.path.join("by-patient",
                        f"{patient_code}-{patient_uuid}",
                        str(y),
                        ymd,
                        fname)
