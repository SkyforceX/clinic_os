from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from unittest.mock import patch

from apps.his_integration.selectors import search_active_his_patients
from apps.his_integration.models import HisPatientSync


class ClinicalDentalPatientSearchTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="clinical_staff",
            password="secret123",
        )
        self.client.force_login(self.user)

    def test_search_active_his_patients_matches_name_and_code(self):
        alpha = HisPatientSync.objects.create(
            his_patient_code="BN000001",
            full_name="Nguyen Van Alpha",
            birth_date_text="01/01",
            birth_year=1990,
            gender_code="0",
            is_active=True,
        )
        beta = HisPatientSync.objects.create(
            his_patient_code="BN999999",
            full_name="Tran Thi Beta",
            birth_date_text="02/02",
            birth_year=1992,
            gender_code="1",
            is_active=True,
        )

        by_name = list(search_active_his_patients(query="Beta"))
        by_code = list(search_active_his_patients(query="BN000001"))

        self.assertEqual([item.id for item in by_name], [beta.id])
        self.assertEqual([item.id for item in by_code], [alpha.id])

    def test_dental_patient_search_api_reads_from_his_integration_dataset(self):
        for index in range(1005):
            HisPatientSync.objects.create(
                his_patient_code=f"BN{index:06d}",
                full_name=f"Patient {index:04d}",
                birth_date_text="01/01",
                birth_year=1990,
                gender_code="0",
                is_active=True,
            )

        target = HisPatientSync.objects.create(
            his_patient_code="BNSPECIAL",
            full_name="Pham Thi Benh Nhan Dac Biet",
            birth_date_text="03/03",
            birth_year=1988,
            gender_code="1",
            is_active=True,
        )

        response = self.client.get(
            reverse("clinical:get_his_all_patients"),
            {"name": "Dac Biet"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        patients = payload["patients"]

        self.assertEqual(len(patients), 1)
        self.assertEqual(patients[0]["id"], target.id)
        self.assertEqual(patients[0]["ma_bn"], "BNSPECIAL")

    def test_dental_patient_search_by_code_does_not_return_partial_mismatch(self):
        target = HisPatientSync.objects.create(
            his_patient_code="BN336100",
            full_name="Dung Ma Trung",
            birth_date_text="03/03",
            birth_year=1988,
            gender_code="1",
            is_active=True,
        )
        HisPatientSync.objects.create(
            his_patient_code="26000061",
            full_name="Nguyen Van Khac",
            birth_date_text="04/04",
            birth_year=1985,
            gender_code="0",
            is_active=True,
        )

        response = self.client.get(
            reverse("clinical:get_his_all_patients"),
            {"code": "3361"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        patients = response.json()["patients"]
        self.assertEqual([item["id"] for item in patients], [target.id])

    @override_settings(DEBUG=True, HIS_LOCAL_SYNC_ENABLED=True)
    @patch("apps.his_integration.web.views.staff.dispatch_his_sync")
    def test_trigger_sync_allows_inline_patient_sync(self, dispatch_his_sync):
        dispatch_his_sync.return_value = {
            "success": True,
            "task_id": "job-123",
            "inline": True,
        }

        response = self.client.post(
            reverse("his_integration:trigger_sync"),
            {
                "sync_type": "patients",
                "run_inline": "true",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertTrue(payload["inline"])
        dispatch_his_sync.assert_called_once()
        self.assertTrue(dispatch_his_sync.call_args.kwargs["run_inline"])
        self.assertEqual(dispatch_his_sync.call_args.kwargs["source"], "local_pg")

    @override_settings(DEBUG=False, HIS_LOCAL_SYNC_ENABLED=False)
    @patch("apps.his_integration.web.views.staff.dispatch_his_sync")
    def test_trigger_sync_defaults_to_mssql_outside_local_debug(self, dispatch_his_sync):
        dispatch_his_sync.return_value = {
            "success": True,
            "task_id": "job-456",
            "inline": True,
        }

        response = self.client.post(
            reverse("his_integration:trigger_sync"),
            {
                "sync_type": "patients",
                "run_inline": "true",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        dispatch_his_sync.assert_called_once()
        self.assertEqual(dispatch_his_sync.call_args.kwargs["source"], "his_mssql")
