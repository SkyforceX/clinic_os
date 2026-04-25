from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from apps.scheduling.policies import SchedulingPolicy


class SchedulingGeneralSettingsAccessTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="executive_user",
            password="secret123",
        )
        executive_group, _ = Group.objects.get_or_create(name="Executives")
        self.user.groups.add(executive_group)
        self.client.force_login(self.user)

    def test_executive_can_manage_general_settings_policy(self):
        self.assertTrue(SchedulingPolicy.can_manage_general_settings(self.user))

    def test_executive_can_open_general_settings_page(self):
        response = self.client.get(reverse("scheduling:general_settings"))

        self.assertEqual(response.status_code, 200)
