from django.contrib.auth import login, logout
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache

from apps.authentication.forms import StaffLoginForm
from apps.authentication.policies import AuthenticationPolicy
from apps.authentication.services.staff_auth import authenticate_staff_credentials


@never_cache
def staff_login(request):
    error = ""
    form = StaffLoginForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        user = authenticate_staff_credentials(
            request=request,
            username=form.cleaned_data["username"],
            password=form.cleaned_data["password"],
        )
        if user is not None:
            login(request, user)
            return redirect(AuthenticationPolicy.get_staff_redirect_name(user))
        error = "Sai ID hoặc mật khẩu"

    return render(
        request,
        "authentication/staff_login_form.html",
        {
            "form": form,
            "error": error,
        },
    )


def staff_logout(request):
    logout(request)
    request.session.flush()
    return redirect("authentication:staff_login")