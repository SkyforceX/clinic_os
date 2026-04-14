import json

import pytest
from django.urls import reverse


@pytest.mark.django_db
@pytest.mark.smoke
def test_reception_lookup_requires_authenticated_operator_session(client):
    response = client.post(
        reverse("reception:ajax_lookup"),
        data=json.dumps({"ma_bn": "BN001"}),
        content_type="application/json",
    )
    assert response.status_code == 401
    payload = response.json()
    assert payload["ok"] is False


@pytest.mark.django_db
@pytest.mark.smoke
def test_reception_stats_requires_authenticated_operator_session(client):
    response = client.get(reverse("reception:ajax_stats"))
    assert response.status_code == 401
    assert response.json()["ok"] is False


@pytest.mark.django_db
@pytest.mark.smoke
def test_reception_tool_renders_for_authenticated_operator_session(reception_session_client):
    response = reception_session_client.get(reverse("reception:checkin_tool"))
    assert response.status_code == 200
    assert "emptyPrompt" in response.content.decode("utf-8")
