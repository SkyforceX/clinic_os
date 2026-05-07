import json
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse


class BookingHisPushSendViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="api_his_exec",
            password="secret123",
        )
        group, _ = Group.objects.get_or_create(name="Executives")
        self.user.groups.add(group)
        self.client.force_login(self.user)

    def test_returns_json_when_appointment_missing(self):
        response = self.client.post(
            reverse("api_his:booking_his_push_send"),
            data=json.dumps({"appointment_id": 999999}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.json()["ok"])

    @patch("apps.api_his.view_api_tools.push_appointment_to_his")
    @patch("apps.api_his.view_api_tools.Appointment")
    def test_returns_json_when_service_raises(self, appointment_model_mock, push_mock):
        appointment_model_mock.objects.select_related.return_value.filter.return_value.first.return_value = Mock()
        push_mock.side_effect = RuntimeError("boom")

        response = self.client.post(
            reverse("api_his:booking_his_push_send"),
            data=json.dumps({"appointment_id": 123}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 500)
        payload = response.json()
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"], "boom")
