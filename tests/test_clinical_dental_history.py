from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.clinical.models import DentalExamination
from apps.clinical.selectors.dental_selectors import get_exam_history_for_patient
from apps.clinical.services.dental_commands import save_dental_examination
from apps.his_integration.models import HisPatientSync


class ClinicalDentalHistoryTests(TestCase):
    def setUp(self):
        self.his_patient = HisPatientSync.objects.create(
            his_patient_code="BN123456",
            full_name="Nguyen Van A",
            birth_date_text="01/01",
            birth_year=1990,
            gender_code="0",
            is_active=True,
        )

    def test_save_dental_examination_creates_new_exam_when_missing_exam_id(self):
        exam = save_dental_examination(
            his_patient_id=self.his_patient.id,
            payload={
                "conclusion": "Lan kham dau",
                "tooth_data": {"11": "S"},
            },
        )

        self.assertEqual(DentalExamination.objects.count(), 1)
        self.assertEqual(exam.his_patient_id, self.his_patient.id)
        self.assertEqual(exam.conclusion, "Lan kham dau")

    def test_save_dental_examination_updates_existing_exam_in_place(self):
        created_at = timezone.now() - timedelta(days=2)
        original = DentalExamination.objects.create(
            his_patient=self.his_patient,
            patient_snapshot={
                "ho_ten": self.his_patient.full_name,
                "ngay_sinh": self.his_patient.birth_date_display,
                "gioi_tinh": self.his_patient.gioi_tinh,
                "ma_bn": self.his_patient.his_patient_code,
            },
            tooth_data={"11": "S"},
            conclusion="Ban dau",
            created_at=created_at,
            updated_at=created_at,
        )

        updated = save_dental_examination(
            his_patient_id=self.his_patient.id,
            payload={
                "dental_exam_id": str(original.id),
                "conclusion": "Da cap nhat",
                "tooth_data": {"11": "M", "12": "K"},
            },
        )

        self.assertEqual(updated.id, original.id)
        self.assertEqual(DentalExamination.objects.count(), 1)

        original.refresh_from_db()
        self.assertEqual(original.conclusion, "Da cap nhat")
        self.assertEqual(original.tooth_data, {"11": "M", "12": "K"})
        self.assertEqual(original.created_at, created_at)
        self.assertGreater(original.updated_at, created_at)

    def test_exam_history_returns_one_item_for_updated_form(self):
        created_at = timezone.now() - timedelta(days=1)
        exam = DentalExamination.objects.create(
            his_patient=self.his_patient,
            patient_snapshot={
                "ho_ten": self.his_patient.full_name,
                "ngay_sinh": self.his_patient.birth_date_display,
                "gioi_tinh": self.his_patient.gioi_tinh,
                "ma_bn": self.his_patient.his_patient_code,
            },
            tooth_data={"21": "S"},
            conclusion="Ket luan cu",
            created_at=created_at,
            updated_at=created_at,
        )

        save_dental_examination(
            his_patient_id=self.his_patient.id,
            payload={
                "dental_exam_id": str(exam.id),
                "conclusion": "Ket luan moi nhat",
                "health_classification": "II",
                "tooth_data": {"21": "M"},
            },
        )

        history = get_exam_history_for_patient(patient_id=self.his_patient.id)

        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["id"], exam.id)
        self.assertEqual(history[0]["conclusion"], "Ket luan moi nhat")
        self.assertEqual(history[0]["health_classification"], "II")
