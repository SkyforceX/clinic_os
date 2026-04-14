from .permissions import user_can_access_ai


def ai_assistant(request):
    """
    Inject `ai_available` vào context của mọi template.
    Dùng để hiện/ẩn link trợ lý AI trong sidebar base template
    mà không cần import logic phân quyền trong từng view.

    Thêm vào settings.py:
        TEMPLATES[0]["OPTIONS"]["context_processors"] += [
            "apps.ai_assistant.context_processors.ai_assistant",
        ]
    """
    return {
        "ai_available": user_can_access_ai(request.user),
    }
