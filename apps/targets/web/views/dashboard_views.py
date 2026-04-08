from datetime import date

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.targets.models import PeriodType, SalesTarget
from apps.targets.policies import TargetsPolicy
from apps.targets.selectors.achievement_selectors import (
    compute_achievement,
    get_available_periods,
    get_leaderboard,
    get_monthly_trend_for_user,
    get_team_dashboard,
)
from apps.targets.services.target_service import add_note, delete_target, upsert_target

User = get_user_model()

MONTH_LABELS = ["T1","T2","T3","T4","T5","T6","T7","T8","T9","T10","T11","T12"]


def _deny(request):
    if not TargetsPolicy.can_view_own(request.user):
        return HttpResponseForbidden("<h2>403 – Yêu cầu đăng nhập.</h2>")
    return None


def _deny_manage(request):
    if not TargetsPolicy.can_manage(request.user):
        return HttpResponseForbidden("<h2>403 – Không có quyền quản lý KPI.</h2>")
    return None


def _current_period():
    today = date.today()
    return today.year, today.month, (today.month - 1) // 3 + 1


# ── Team Dashboard ─────────────────────────────────────────────────────────────

@login_required(login_url="authentication:staff_login")
def team_dashboard(request):
    denied = _deny(request)
    if denied:
        return denied

    can_manage = TargetsPolicy.can_manage(request.user)
    can_view_all = TargetsPolicy.can_view_all(request.user)

    today  = date.today()
    year   = int(request.GET.get("year")   or today.year)
    period_type = request.GET.get("pt", PeriodType.MONTHLY)
    period_number = int(request.GET.get("p") or today.month)

    team_data   = get_team_dashboard(period_type, year, period_number) if can_view_all else []
    leaderboard = get_leaderboard(period_type, year, period_number)    if can_view_all else []

    # Own target
    own_target = SalesTarget.objects.filter(
        user=request.user,
        period_type=period_type,
        year=year,
        period_number=period_number,
    ).first()
    own_achievement = compute_achievement(own_target) if own_target else None

    # Monthly trend (own)
    trend = get_monthly_trend_for_user(request.user.id, year)
    trend_actual  = [r["actual"]  for r in trend]
    trend_target  = [r["target"]  for r in trend]

    # All sales users (for manager to assign targets)
    sales_users = []
    if can_manage:
        sales_users = list(
            User.objects.filter(
                groups__name__in=["Sales Team", "Sales"]
            ).distinct().order_by("first_name", "username")
        )

    available_periods = get_available_periods(period_type)
    available_years   = sorted({y for y, _ in available_periods} | {today.year}, reverse=True)

    period_numbers = {
        PeriodType.MONTHLY:   list(range(1, 13)),
        PeriodType.QUARTERLY: list(range(1, 5)),
        PeriodType.YEARLY:    [1],
    }.get(period_type, [])

    return render(request, "targets/staff/dashboard.html", {
        "year":            year,
        "period_type":     period_type,
        "period_number":   period_number,
        "period_types":    PeriodType.choices,
        "period_numbers":  period_numbers,
        "available_years": available_years,
        "team_data":       team_data,
        "leaderboard":     leaderboard,
        "own_target":      own_target,
        "own_achievement": own_achievement,
        "trend_actual":    trend_actual,
        "trend_target":    trend_target,
        "month_labels":    MONTH_LABELS,
        "can_manage":      can_manage,
        "can_view_all":    can_view_all,
        "sales_users":     sales_users,
        "PeriodType":      PeriodType,
        "today":           today,
    })


# ── Target CRUD ────────────────────────────────────────────────────────────────

@login_required(login_url="authentication:staff_login")
def target_form(request, target_id=None):
    """Tạo mới hoặc sửa target — GET hiển thị form, POST lưu."""
    denied = _deny_manage(request)
    if denied:
        return denied

    target = get_object_or_404(SalesTarget, pk=target_id) if target_id else None

    today = date.today()
    sales_users = list(
        User.objects.filter(
            groups__name__in=["Sales Team", "Sales"]
        ).distinct().order_by("first_name", "username")
    )

    if request.method == "POST":
        p = request.POST
        user_id_raw = p.get("user_id") or ""
        user_id = int(user_id_raw) if user_id_raw.isdigit() else None

        try:
            obj = upsert_target(
                actor=request.user,
                user_id=user_id,
                period_type=p.get("period_type", PeriodType.MONTHLY),
                year=int(p.get("year") or today.year),
                period_number=int(p.get("period_number") or 1),
                revenue_target=int(p.get("revenue_target") or 0),
                contract_count_target=int(p.get("contract_count_target") or 0),
                quotation_count_target=int(p.get("quotation_count_target") or 0),
                pax_target=int(p.get("pax_target") or 0),
                new_client_target=int(p.get("new_client_target") or 0),
                renewal_target=int(p.get("renewal_target") or 0),
                avg_deal_size_target=int(p.get("avg_deal_size_target") or 0),
                notes=p.get("notes") or "",
            )
            messages.success(request, f"Đã lưu KPI: {obj}")
            return redirect("targets:dashboard")
        except Exception as exc:
            messages.error(request, f"Lỗi: {exc}")

    return render(request, "targets/staff/target_form.html", {
        "target":      target,
        "sales_users": sales_users,
        "period_types": PeriodType.choices,
        "today":       today,
        "years":       [today.year - 1, today.year, today.year + 1],
    })


@login_required(login_url="authentication:staff_login")
@require_POST
def target_delete(request, target_id):
    denied = _deny_manage(request)
    if denied:
        return denied
    target = get_object_or_404(SalesTarget, pk=target_id)
    delete_target(actor=request.user, target=target)
    messages.success(request, "Đã xóa KPI.")
    return redirect("targets:dashboard")


@login_required(login_url="authentication:staff_login")
def target_detail(request, target_id):
    denied = _deny(request)
    if denied:
        return denied

    target = get_object_or_404(SalesTarget, pk=target_id)

    # Sales chỉ xem target của mình
    if not TargetsPolicy.can_view_all(request.user):
        if target.user_id != request.user.id:
            return HttpResponseForbidden()

    achievement = compute_achievement(target)
    trend       = get_monthly_trend_for_user(target.user_id, target.year)
    notes       = target.target_notes.select_related("author").all()

    if request.method == "POST" and request.POST.get("body"):
        add_note(actor=request.user, target=target, body=request.POST["body"])
        messages.success(request, "Đã thêm ghi chú.")
        return redirect("targets:detail", target_id=target.id)

    return render(request, "targets/staff/target_detail.html", {
        "target":      target,
        "achievement": achievement,
        "trend":       trend,
        "month_labels": MONTH_LABELS,
        "trend_actual": [r["actual"] for r in trend],
        "trend_target": [r["target"] for r in trend],
        "notes":       notes,
        "can_manage":  TargetsPolicy.can_manage(request.user),
    })


# ── Bulk Monthly Setup (AJAX) ──────────────────────────────────────────────────

@login_required(login_url="authentication:staff_login")
@require_POST
def ajax_bulk_monthly(request):
    denied = _deny_manage(request)
    if denied:
        return JsonResponse({"ok": False, "error": "Không có quyền."}, status=403)

    import json
    data = json.loads(request.body)
    user_id = data.get("user_id") or None
    year = int(data.get("year") or date.today().year)
    revenues = data.get("revenues", [0] * 12)
    contracts = data.get("contracts", [0] * 12)

    if len(revenues) != 12:
        return JsonResponse({"ok": False, "error": "Cần 12 phần tử."}, status=400)

    from apps.targets.services.target_service import bulk_upsert_monthly_targets
    bulk_upsert_monthly_targets(
        actor=request.user,
        user_id=user_id,
        year=year,
        monthly_revenues=[int(r) for r in revenues],
        monthly_contracts=[int(c) for c in contracts],
    )
    return JsonResponse({"ok": True, "saved": 12})
