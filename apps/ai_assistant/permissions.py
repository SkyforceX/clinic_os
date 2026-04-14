from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.conf import settings


AI_ASSISTANT_ALLOWED_GROUPS = getattr(
    settings, "AI_ASSISTANT_ALLOWED_GROUPS", ["Executives", "Executive"]
)


def user_can_access_ai(user):
    """
    Trả về True nếu user là superadmin hoặc thuộc nhóm được phép dùng AI assistant.
    """
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=AI_ASSISTANT_ALLOWED_GROUPS).exists()


class AiAssistantAccessMixin(LoginRequiredMixin):
    """
    Mixin yêu cầu đăng nhập và kiểm tra quyền truy cập AI assistant.
    Chỉ Executives và superadmin mới được phép.
    """

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        # super() đã xử lý redirect nếu chưa đăng nhập
        if not request.user.is_authenticated:
            return response
        if not user_can_access_ai(request.user):
            raise PermissionDenied
        return response
