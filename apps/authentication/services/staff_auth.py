from django.contrib.auth import authenticate


def authenticate_staff_credentials(*, request, username, password):
    return authenticate(request, username=username, password=password)