from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from apps.notifications.models import Notification


@login_required
@require_GET
def unread_count(request):
    """
    GET /notifications/unread-count/
    Trả về số thông báo chưa đọc — dùng để init badge khi page load.
    (Sau khi WS connect, badge cập nhật qua WebSocket, không cần poll nữa.)
    """
    count = Notification.objects.filter(
        recipient=request.user, is_read=False
    ).count()
    return JsonResponse({"count": count})
