import json
from datetime import date

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.tasks.models import Task, TaskPriority, TaskStage, TaskComment
from apps.tasks.policies import TaskPolicy
from apps.tasks.selectors.task_selectors import build_pipeline_data, get_tasks_for_user
from apps.tasks.services.task_service import (
    add_comment, assign_task, create_task, delete_task, move_stage, update_task,
)

User = get_user_model()


def _deny(request):
    if not request.user.is_authenticated:
        return redirect("authentication:staff_login")
    return None


def _safe_date(raw) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except (ValueError, TypeError):
        return None


# ── Pipeline board ─────────────────────────────────────────────────────────────

@login_required(login_url="authentication:staff_login")
def pipeline_board(request):
    user = request.user

    filters = {
        "search":      request.GET.get("q") or None,
        "priority":    request.GET.get("priority") or None,
        "assignee_id": request.GET.get("assignee") or None,
        "overdue":     request.GET.get("overdue") == "1",
    }

    try:
        done_limit = int(request.GET.get("done_limit") or 10)
        done_limit = max(5, min(done_limit, 100))
    except (ValueError, TypeError):
        done_limit = 10

    pipeline = build_pipeline_data(user, filters=filters, done_limit=done_limit)
    can_create = TaskPolicy.can_create_task(user)

    assignable_users = []
    if can_create:
        assignable_users = list(TaskPolicy.get_assignable_users(user))

    # Filter user list for filter dropdown (all users visible to me)
    filter_users = assignable_users if TaskPolicy.can_view_all_tasks(user) else []

    return render(request, "tasks/staff/pipeline.html", {
        "pipeline":        pipeline,
        "can_create":      can_create,
        "can_view_all":    TaskPolicy.can_view_all_tasks(user),
        "assignable_users": assignable_users,
        "filter_users":    filter_users,
        "priorities":      TaskPriority.choices,
        "stages":          TaskStage.choices,
        "filters":         filters,
        "done_limit":      done_limit,
        "today":           date.today(),
    })


# ── Task detail ────────────────────────────────────────────────────────────────

@login_required(login_url="authentication:staff_login")
def task_detail(request, task_id):
    task = get_object_or_404(Task.objects.select_related("created_by","assignee").prefetch_related("watchers","comments__author","activities__actor"), pk=task_id)

    if not TaskPolicy.can_view_task(request.user, task):
        return HttpResponseForbidden()

    can_edit          = TaskPolicy.can_edit_task(request.user, task)
    can_update_stage  = TaskPolicy.can_update_stage(request.user, task)
    can_delete        = TaskPolicy.can_delete_task(request.user, task)
    assignable_users  = list(TaskPolicy.get_assignable_users(request.user)) if can_edit else []

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "comment":
            body = (request.POST.get("body") or "").strip()
            if body:
                add_comment(actor=request.user, task=task, body=body,
                            is_internal=request.POST.get("is_internal") == "1")
                messages.success(request, "Đã thêm bình luận.")
            return redirect("tasks:detail", task_id=task.pk)

        if action == "move" and can_update_stage:
            new_stage = request.POST.get("stage")
            if new_stage in dict(TaskStage.choices):
                move_stage(actor=request.user, task=task, new_stage=new_stage)
                messages.success(request, f"Đã chuyển sang: {dict(TaskStage.choices)[new_stage]}")
            return redirect("tasks:detail", task_id=task.pk)

        if action == "edit" and can_edit:
            update_task(
                actor=request.user,
                task=task,
                title=(request.POST.get("title") or task.title).strip(),
                description=(request.POST.get("description") or "").strip(),
                priority=request.POST.get("priority") or task.priority,
                due_date=_safe_date(request.POST.get("due_date")),
                start_date=_safe_date(request.POST.get("start_date")),
                tags=(request.POST.get("tags") or ""),
                estimated_hours=request.POST.get("estimated_hours") or None,
                actual_hours=request.POST.get("actual_hours") or None,
            )
            aid = request.POST.get("assignee_id")
            assign_task(actor=request.user, task=task, assignee_id=int(aid) if aid else None)
            messages.success(request, "Đã cập nhật công việc.")
            return redirect("tasks:detail", task_id=task.pk)

        if action == "delete" and can_delete:
            title = task.title
            delete_task(actor=request.user, task=task)
            messages.success(request, f"Đã xóa: {title}")
            return redirect("tasks:board")

    return render(request, "tasks/staff/task_detail.html", {
        "task":            task,
        "can_edit":        can_edit,
        "can_update_stage": can_update_stage,
        "can_delete":      can_delete,
        "assignable_users": assignable_users,
        "stages":          TaskStage.choices,
        "priorities":      TaskPriority.choices,
        "today":           date.today(),
    })


# ── Create task ────────────────────────────────────────────────────────────────

@login_required(login_url="authentication:staff_login")
def task_create(request):
    if not TaskPolicy.can_create_task(request.user):
        return HttpResponseForbidden("<h2>403 – Không có quyền tạo công việc.</h2>")

    assignable_users = list(TaskPolicy.get_assignable_users(request.user))

    if request.method == "POST":
        p = request.POST
        title = (p.get("title") or "").strip()
        if not title:
            messages.error(request, "Vui lòng nhập tiêu đề công việc.")
        else:
            aid = p.get("assignee_id")
            task = create_task(
                actor=request.user,
                title=title,
                description=(p.get("description") or "").strip(),
                assignee_id=int(aid) if aid else None,
                priority=p.get("priority") or TaskPriority.MEDIUM,
                due_date=_safe_date(p.get("due_date")),
                start_date=_safe_date(p.get("start_date")),
                estimated_hours=p.get("estimated_hours") or None,
                tags=(p.get("tags") or "").strip(),
            )
            messages.success(request, f"Đã tạo công việc: {task.title}")
            return redirect("tasks:board")

    return render(request, "tasks/staff/task_form.html", {
        "assignable_users": assignable_users,
        "priorities":       TaskPriority.choices,
        "today":            date.today(),
    })


# ── AJAX: move stage (drag-drop) ───────────────────────────────────────────────

@login_required(login_url="authentication:staff_login")
@require_POST
def ajax_move_stage(request, task_id):
    task = get_object_or_404(Task, pk=task_id)
    if not TaskPolicy.can_update_stage(request.user, task):
        return JsonResponse({"ok": False, "error": "Không có quyền"}, status=403)
    body = json.loads(request.body)
    new_stage = body.get("stage")
    if new_stage not in dict(TaskStage.choices):
        return JsonResponse({"ok": False, "error": "Stage không hợp lệ"}, status=400)
    move_stage(actor=request.user, task=task, new_stage=new_stage)
    return JsonResponse({"ok": True, "stage": new_stage})


# ── AJAX: quick update order ───────────────────────────────────────────────────

@login_required(login_url="authentication:staff_login")
@require_POST
def ajax_reorder(request):
    body = json.loads(request.body)
    ordered = body.get("ordered", [])  # list of {id, stage_order}
    for item in ordered:
        Task.objects.filter(pk=item["id"]).update(stage_order=item["order"])
    return JsonResponse({"ok": True})


# ── AJAX: load more done tasks ────────────────────────────────────────────────

@login_required(login_url="authentication:staff_login")
def ajax_load_more_done(request):
    stage  = request.GET.get("stage", TaskStage.DONE)
    offset = int(request.GET.get("offset", 10))
    limit  = int(request.GET.get("limit", 10))

    qs = get_tasks_for_user(request.user, {"stage": stage})
    tasks = list(
        qs.filter(stage=stage)
        .order_by("stage_order", "-priority", "due_date")
        .values("id", "title", "priority", "due_date", "assignee__first_name", "assignee__last_name", "assignee__username")
        [offset:offset + limit]
    )

    total = qs.filter(stage=stage).count()
    return JsonResponse({"tasks": tasks, "total": total, "has_more": offset + limit < total})
