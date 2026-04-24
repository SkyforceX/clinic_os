import os
import unicodedata
from datetime import date, datetime

from django.db import models
from django.utils.text import slugify


def pathology_upload_path(instance, filename):
    def normalize(text):
        text = str(text or "").replace("đ", "d").replace("Đ", "D")
        text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("utf-8")
        return slugify(text, allow_unicode=False).replace("-", "_")

    patient = getattr(instance, "his_patient", None) or getattr(instance, "patient", None)
    patient_code = normalize(
        getattr(patient, "his_patient_code", None)
        or getattr(patient, "ma_bn", "unknown")
    )
    full_name = normalize(
        getattr(patient, "full_name", None)
        or getattr(patient, "ho_ten", "unknown")
    )
    location = normalize(getattr(instance, "location", "unknown"))

    result_date = instance.result_date
    if isinstance(result_date, str):
        result_date = datetime.strptime(result_date, "%Y-%m-%d").date()
    elif result_date is None:
        result_date = date.today()

    result_date_str = result_date.strftime("%d%m%Y")
    folder_date_str = result_date.strftime("%m-%Y")
    unique_suffix = datetime.now().strftime("%H%M%S%f")[:9]
    ext = os.path.splitext(filename)[1] or ".pdf"
    new_filename = f"{patient_code}_{full_name}_{result_date_str}_{location}_{unique_suffix}{ext}"
    return f"uploads/pathology_pdfs/{folder_date_str}/{new_filename}"


class DentalExamination(models.Model):
    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clinical_dental_examinations",
    )
    his_patient = models.ForeignKey(
        "his_integration.HisPatientSync",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dental_examinations",
        verbose_name="Bệnh nhân HIS",
    )
    # nullable để hỗ trợ khách lẻ không thuộc công ty nào
    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clinical_dental_examinations",
    )
    # Snapshot thông tin hành chính tại thời điểm khám
    patient_snapshot = models.JSONField(default=dict, blank=True)

    additional_notes = models.TextField(blank=True)
    tooth_data = models.JSONField(default=dict)
    tooth_loss_classification = models.CharField(
        max_length=3,
        choices=[("I", "I"), ("II", "II"), ("III", "III"), ("IV", "IV"), ("V", "V")],
        blank=True,
    )
    other_oral_conditions = models.TextField(blank=True)
    chewing_ability = models.DecimalField(max_digits=5, decimal_places=0, null=True, blank=True)
    health_classification = models.CharField(
        max_length=3,
        choices=[("I", "I"), ("II", "II"), ("III", "III"), ("IV", "IV"), ("V", "V")],
        blank=True,
    )
    conclusion = models.TextField(blank=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        db_table = "clinical_dentalexamination"
        ordering = ["-created_at", "-id"]
        verbose_name = "Dental Examination"
        verbose_name_plural = "Dental Examinations"

    def __str__(self):
        patient = self.his_patient or self.patient
        patient_name = (
            getattr(patient, "full_name", None)
            or getattr(patient, "ho_ten", None)
            or "unknown"
        )
        patient_code = (
            getattr(patient, "his_patient_code", None)
            or getattr(patient, "ma_bn", None)
            or ""
        )
        return f"Examination - {patient_name} ({patient_code})"


class ToothNotation(models.Model):
    code = models.CharField(max_length=5, unique=True)
    description_vi = models.CharField(max_length=200)
    description_en = models.CharField(max_length=200)

    class Meta:
        db_table = "clinical_toothnotation"
        ordering = ["code"]
        verbose_name = "Tooth Notation"
        verbose_name_plural = "Tooth Notations"

    def __str__(self):
        return f"{self.code}: {self.description_vi}"


class PathologyResult(models.Model):
    EVALUATION_CHOICES = [
        ("normal", "Bình thường"),
        ("follow", "Theo dõi"),
    ]

    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clinical_pathology_results",
    )
    his_patient = models.ForeignKey(
        "his_integration.HisPatientSync",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pathology_results",
        verbose_name="Bệnh nhân HIS",
    )
    location = models.CharField(max_length=255)
    file_url = models.FileField(upload_to=pathology_upload_path)
    result_date = models.DateField(null=True, blank=True)
    auto_extracted_conclusion = models.TextField(blank=True, null=True)
    manual_conclusion = models.TextField(blank=True, null=True)
    evaluation = models.CharField(
        max_length=10,
        choices=EVALUATION_CHOICES,
        blank=True,
        null=True,
        verbose_name="Đánh giá",
    )
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        db_table = "clinic_pathologyresult"
        managed = False
        ordering = ["-result_date", "-id"]
        verbose_name = "Pathology Result"
        verbose_name_plural = "Pathology Results"

    def __str__(self):
        patient_name = (
            getattr(self.his_patient, "full_name", None)
            or getattr(self.patient, "ho_ten", None)
            or "unknown"
        )
        return f"Kết quả GPB - {patient_name} ({self.location})"
