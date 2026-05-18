from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings

from apps.booking.services.his_appointment_push import (
    build_his_appointment_push_body,
    push_appointment_to_his,
)


def _build_appointment():
    company = SimpleNamespace(name="Cong ty ABC")
    schedule_slot = SimpleNamespace(
        date=date(2026, 5, 6),
        shift="AM",
        contract=SimpleNamespace(company=company),
        quotation=None,
    )
    his_patient = SimpleNamespace(
        his_patient_code="BN001",
        full_name="Nguyen Van A",
        birth_year=1990,
        birth_date_text="01/01/1990",
        gender_code="0",
        phone="0909123456",
        address="123 Duong ABC",
    )
    return SimpleNamespace(id=321, his_patient_sync=his_patient, patient=None, schedule_slot=schedule_slot)


@override_settings(
    HIS_LOCAL_SYNC_ENABLED=False,
    HIS_APPOINTMENT_PUSH={
        "ENABLED": True,
        "URL": "http://example.test/api/AppService",
        "CMD": "API_DanhSachLichHen.Insert",
        "TIMEOUT": 8,
        "DEFAULT_DOCTOR_CODE": "",
        "DEFAULT_DEPARTMENT_CODE": "KSK",
        "DEFAULT_USER_CODE": "clinic-os",
        "DEFAULT_CLIENT_SOURCE_CODE": "WEB",
        "DEFAULT_CONTENT": "Dang ky kham doan tu Clinic OS",
        "DEFAULT_REASON": "Dang ky KSK",
        "DEFAULT_NOTE": "",
        "DEFAULT_APPOINTMENT_TYPE": 0,
        "MORNING_START": "07:00:00",
        "MORNING_END": "11:30:00",
        "AFTERNOON_START": "13:00:00",
        "AFTERNOON_END": "17:00:00",
    }
)
class BookingHisAppointmentPushTests(SimpleTestCase):
    def test_build_his_payload_from_his_patient(self):
        body = build_his_appointment_push_body(_build_appointment())
        lichhen = body["data"]["lichhen"]

        self.assertEqual(body["cmd"], "API_DanhSachLichHen.Insert")
        self.assertEqual(lichhen["MaBenhNhan"], "BN001")
        self.assertEqual(lichhen["HoTen"], "Nguyen Van A")
        self.assertEqual(lichhen["MaKhoa"], "KSK")
        self.assertEqual(lichhen["MaNguonKhach"], "WEB")
        self.assertEqual(lichhen["NgayBatDau"], "2026-05-06 07:00:00")
        self.assertEqual(lichhen["NgayKetThuc"], "2026-05-06 11:30:00")
        self.assertEqual(lichhen["IDLichHenWeb"], 321)

    @patch("apps.booking.services.his_appointment_push.requests.post")
    def test_push_appointment_success(self, mock_post):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"code": 1, "msg": "OK", "data": [{"ID": 2865}]}
        response.raise_for_status.return_value = None
        mock_post.return_value = response

        result = push_appointment_to_his(_build_appointment())

        self.assertTrue(result.success)
        self.assertTrue(result.attempted)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.response_data, {"code": 1, "msg": "OK", "data": [{"ID": 2865}]})
        mock_post.assert_called_once()

    @override_settings(
        HIS_LOCAL_SYNC_ENABLED=False,
        HIS_APPOINTMENT_PUSH={"ENABLED": False, "URL": "http://example.test/api/AppService"},
    )
    def test_push_appointment_skips_when_disabled(self):
        result = push_appointment_to_his(_build_appointment())

        self.assertFalse(result.success)
        self.assertFalse(result.attempted)
        self.assertEqual(result.skipped_reason, "HIS appointment push is disabled.")
