from django.http import HttpResponseNotAllowed, JsonResponse


def approval_modal(request):
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])

    return JsonResponse(
        {
            "success": False,
            "message": "Màn hình approval modal chưa được triển khai trong bước refactor này.",
        },
        status=501,
    )