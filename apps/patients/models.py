import uuid

from django.db import models


class Patient(models.Model):
    """
    Normalized patient model.

    Phase 2.1:
    - Chuyển ownership từ bảng legacy `clinic_patient` sang bảng mới `patients_patient`
    - Giữ nguyên PK để data migration an toàn và các FK có thể chuyển dần ở phase sau
    """

    id = models.AutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, null=False, blank=True)
    ma_bn = models.CharField(max_length=20, unique=True)
    ho_ten = models.CharField(max_length=100)
    gioi_tinh = models.CharField(max_length=10)
    ngay_sinh = models.DateField()
    phone = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    dia_chi = models.TextField(blank=True, null=True)
    so_cmnd = models.CharField(max_length=20, blank=True, null=True)
    so_bhyt = models.CharField(max_length=20, blank=True, null=True)
    ma_the_bhyt = models.CharField(max_length=20, blank=True, null=True)
    password = models.CharField(max_length=128, blank=True, null=True)
    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.SET_NULL,
        related_name="patients",
        blank=True,
        null=True,
    )
    position = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "patients_patient"
        ordering = ["id"]
        verbose_name = "Patient"
        verbose_name_plural = "Patients"

    def __str__(self):
        return f"{self.ho_ten} ({self.ma_bn})"


class PatientCompanyHistory(models.Model):
    patient = models.ForeignKey("patients.Patient", on_delete=models.CASCADE)
    company = models.ForeignKey("organizations.Company", on_delete=models.CASCADE)
    from_date = models.DateField()
    to_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "patients_patientcompanyhistory"
        ordering = ["-from_date", "-created_at"]
        verbose_name = "Patient Company History"
        verbose_name_plural = "Patient Company Histories"