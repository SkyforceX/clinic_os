from django.shortcuts import render

def custom_page_not_found(request, exception):
    return render(request, "core/404.html", status=404)

def custom_server_error(request):
    return render(request, "core/500.html", status=500)

def custom_permission_denied(request, exception):
    return render(request, "core/403.html", status=403)

# def custom_bad_request(request, exception):
#     return render(request, "core/400.html", status=400)

def custom_csrf_failure(request, reason=""):
    return render(request, "core/403_csrf.html", status=403, context={"reason": reason})
