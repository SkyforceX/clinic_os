import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group


@pytest.fixture
def superuser(db):
    user_model = get_user_model()
    return user_model.objects.create_superuser(
        username="pytest_admin",
        email="pytest_admin@example.com",
        password="pytest-pass-123",
    )


@pytest.fixture
def auth_client(client, superuser):
    client.force_login(superuser)
    return client


@pytest.fixture
def reception_operator(db):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="reception_operator",
        email="reception@example.com",
        password="pytest-pass-123",
        is_staff=True,
    )
    group, _ = Group.objects.get_or_create(name="Operations Team")
    user.groups.add(group)
    return user


@pytest.fixture
def reception_session_client(client, reception_operator):
    session = client.session
    session["reception_operator_id"] = reception_operator.pk
    session.save()
    return client
