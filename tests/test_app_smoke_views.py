import pytest
from django.urls import reverse


PUBLIC_PAGES = [
    "authentication:patient_login",
    "authentication:staff_login",
    "reception:checkin_tool",
    "quality:incident_report_public",
]

AUTH_PAGES = [
    "dashboard:overview",
    "procedures:list",
    "procedures:create",
    "contract:quotation_list",
    "contract:corporate_contract_list",
    "hrm:employee_list",
    "hrm:work_schedule_month",
    "approvals:my_requests",
    "catalogs:package_list",
    "organizations:company_list",
]


@pytest.mark.smoke
@pytest.mark.parametrize("route_name", PUBLIC_PAGES)
def test_public_pages_render_without_server_error(client, route_name):
    response = client.get(reverse(route_name))
    assert response.status_code == 200


@pytest.mark.django_db
@pytest.mark.smoke
@pytest.mark.parametrize("route_name", AUTH_PAGES)
def test_authenticated_pages_render_without_server_error(auth_client, route_name):
    response = auth_client.get(reverse(route_name))
    assert response.status_code == 200
