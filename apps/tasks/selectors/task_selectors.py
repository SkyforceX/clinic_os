from django.db.models import Count, Q

from apps.tasks.models import Task, TaskStage
from apps.tasks.policies import TaskPolicy

PIPELINE_STAGES = [
    TaskStage.TODO,
    TaskStage.IN_PROGRESS,
    TaskStage.IN_REVIEW,
    TaskStage.DONE,
    TaskStage.CANCELLED,
]


def get_tasks_for_user(user, filters: dict | None = None):
    """Base queryset theo phân quyền."""
    filters = filters or {}
    qs = Task.objects.select_related("created_by", "assignee").prefetch_related("watchers")

    if not TaskPolicy.can_view_all_tasks(user):
        qs = qs.filter(
            Q(created_by=user) | Q(assignee=user) | Q(watchers=user)
        ).distinct()

    if filters.get("stage"):
        qs = qs.filter(stage=filters["stage"])
    if filters.get("priority"):
        qs = qs.filter(priority=filters["priority"])
    if filters.get("assignee_id"):
        qs = qs.filter(assignee_id=filters["assignee_id"])
    if filters.get("search"):
        qs = qs.filter(
            Q(title__icontains=filters["search"])
            | Q(description__icontains=filters["search"])
            | Q(tags__icontains=filters["search"])
        )
    if filters.get("overdue"):
        from django.utils import timezone
        qs = qs.filter(due_date__lt=timezone.now().date()).exclude(stage__in=[TaskStage.DONE, TaskStage.CANCELLED])

    return qs


def build_pipeline_data(user, filters: dict | None = None, done_limit: int = 10) -> list[dict]:
    """
    Trả về list theo thứ tự PIPELINE_STAGES, mỗi stage có:
      - stage, label, color, icon
      - tasks: queryset (DONE/CANCELLED giới hạn done_limit để tránh trang quá dài)
      - total_count: tổng thực sự (kể cả bị ẩn)
      - has_more: bool (DONE/CANCELLED có nhiều hơn done_limit)
    """
    base = get_tasks_for_user(user, filters)

    STAGE_META = {
        TaskStage.TODO:        {"label": "Cần làm",           "color": "#6c757d", "icon": "fa-circle-dot",     "bg": "#f8f9fa"},
        TaskStage.IN_PROGRESS: {"label": "Đang thực hiện",    "color": "#2e86c1", "icon": "fa-spinner",        "bg": "#e8f4fd"},
        TaskStage.IN_REVIEW:   {"label": "Chờ kiểm tra",      "color": "#e67e22", "icon": "fa-magnifying-glass","bg": "#fef9ec"},
        TaskStage.DONE:        {"label": "Hoàn thành",        "color": "#27ae60", "icon": "fa-circle-check",   "bg": "#eafaf1"},
        TaskStage.CANCELLED:   {"label": "Đã hủy",            "color": "#dc3545", "icon": "fa-ban",            "bg": "#fdf2f2"},
    }

    result = []
    for stage in PIPELINE_STAGES:
        stage_qs = base.filter(stage=stage).order_by("stage_order", "-priority", "due_date")
        total    = stage_qs.count()

        # DONE và CANCELLED: giới hạn hiển thị, tránh trang quá dài
        is_closed = stage in (TaskStage.DONE, TaskStage.CANCELLED)
        if is_closed:
            tasks    = list(stage_qs[:done_limit])
            has_more = total > done_limit
        else:
            tasks    = list(stage_qs)
            has_more = False

        meta = STAGE_META[stage]
        result.append({
            "stage":       stage,
            "label":       meta["label"],
            "color":       meta["color"],
            "icon":        meta["icon"],
            "bg":          meta["bg"],
            "tasks":       tasks,
            "total_count": total,
            "shown_count": len(tasks),
            "has_more":    has_more,
            "is_closed":   is_closed,
        })

    return result


def get_my_tasks_summary(user) -> dict:
    """Tổng hợp nhanh cho dashboard cá nhân."""
    base = Task.objects.filter(assignee=user)
    return {
        "todo":        base.filter(stage=TaskStage.TODO).count(),
        "in_progress": base.filter(stage=TaskStage.IN_PROGRESS).count(),
        "in_review":   base.filter(stage=TaskStage.IN_REVIEW).count(),
        "done_month":  base.filter(stage=TaskStage.DONE).count(),
        "overdue":     base.filter(
            stage__in=[TaskStage.TODO, TaskStage.IN_PROGRESS, TaskStage.IN_REVIEW],
            due_date__lt=__import__("django.utils.timezone", fromlist=["now"]).now().date() if False else __import__("datetime").date.today(),
        ).count(),
    }
