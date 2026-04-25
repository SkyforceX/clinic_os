from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from apps.contract.policies import ContractPolicy
from apps.hrm.policies import HRMPolicy
from apps.scheduling.policies import SchedulingPolicy


class ExecutiveSidebarAccessTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="exec_sidebar_user",
            password="secret123",
        )
        executive_group, _ = Group.objects.get_or_create(name="Executives")
        self.user.groups.add(executive_group)
        self.client.force_login(self.user)

    def test_executive_can_open_sidebar_routes(self):
        routes = [
            "ai_assistant:index",
            "scheduling:general_settings",
            "api_his:api_playground",
            "targets:dashboard",
            "hrm:employee_list",
            "hrm:employee_create",
            "hrm:department_list",
            "hrm:position_list",
            "hrm:doctor_schedule_list",
            "contract:create_proposal",
            "contract:create_contract",
        ]

        for route_name in routes:
            with self.subTest(route=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)

    def test_executive_policy_access_matches_sidebar_expectations(self):
        self.assertTrue(ContractPolicy.can_create_contract(self.user))
        self.assertTrue(SchedulingPolicy.can_manage_quote_schedule(self.user, owner_user_id=999))
        self.assertTrue(SchedulingPolicy.can_end_schedule(self.user, owner_user_id=999))
        self.assertTrue(HRMPolicy.can_view_employee_list(self.user))
        self.assertTrue(HRMPolicy.can_create_employee(self.user))
        self.assertTrue(HRMPolicy.can_manage_departments(self.user))
        self.assertTrue(HRMPolicy.can_manage_positions(self.user))
