"""
apps/record_completion/web/views/pipeline_views.py
"""

import json

from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST

from apps.record_completion.models import (
    LOG_ACTION_RETURN,
    RecordCompletion,
    STEP_CONFIGS,
    TOTAL_STEPS,
)
from apps.record_completion.policies import RecordCompletionPolicy
from apps.record_completion.selectors.completion_selectors import (
    ensure_completions_for_company,
    get_active_companies_summary,
    get_checkin_stats_for_company,
    get_company_for_pipeline,
    get_completion_with_logs,
    get_pipeline_for_company,
)
from apps.record_completion.services.completion_service import (
    AdvanceStepError,
    ReturnStepError,
    advance_step,
    return_step,
)


@login_required(login_url="authentication:staff_login")
def company_list_view(request):
    if not RecordCompletionPolicy.can_view(request.user):
        raise Http404
    context = {
        "summaries":  get_active_companies_summary(),
        "page_title": "Hoàn tất hồ sơ",
    }
    return render(request, "record_completion/staff/company_list.html", context)


@login_required(login_url="authentication:staff_login")
def pipeline_view(request, company_id: int):
    if not RecordCompletionPolicy.can_view(request.user):
        raise Http404

    company = get_company_for_pipeline(company_id=company_id)
    if not company:
        raise Http404("Không tìm thấy công ty.")

    ensure_completions_for_company(company)

    ma_bn_filter  = request.GET.get("q", "").strip()
    pipeline      = get_pipeline_for_company(company, ma_bn_filter=ma_bn_filter)
    checkin_stats = get_checkin_stats_for_company(company)
    advanceable   = RecordCompletionPolicy.get_advanceable_steps(request.user)

    context = {
        "company":                company,
        "pipeline":               pipeline,
        "checkin_stats":          checkin_stats,
        "step_configs":           STEP_CONFIGS,
        "total_steps":            TOTAL_STEPS,
        "advanceable_steps":      advanceable,
        "advanceable_steps_json": json.dumps(sorted(advanceable)),
        "ma_bn_filter":           ma_bn_filter,
        "page_title":             f"Hồ sơ – {company.name}",
    }
    return render(request, "record_completion/staff/pipeline.html", context)


@require_POST
@login_required(login_url="authentication:staff_login")
def advance_step_view(request, completion_id: int):
    record = get_object_or_404(
        RecordCompletion.objects.select_related("checkin_record", "company"),
        pk=completion_id,
    )

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        body = {}

    note       = (body.get("note")       or request.POST.get("note",       "")).strip()
    ma_bn_scan = (body.get("ma_bn_scan") or request.POST.get("ma_bn_scan", "")).strip()

    try:
        record = advance_step(record=record, actor=request.user, note=note, ma_bn_scan=ma_bn_scan)
    except AdvanceStepError as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=400)

    advanceable = RecordCompletionPolicy.get_advanceable_steps(request.user)
    card_html   = render_to_string(
        "record_completion/staff/_card.html",
        {"completion": record, "advanceable_steps": advanceable},
        request=request,
    )
    return JsonResponse({
        "success":      True,
        "new_step":     record.current_step,
        "is_completed": record.is_completed,
        "card_html":    card_html,
    })


@require_POST
@login_required(login_url="authentication:staff_login")
def return_step_view(request, completion_id: int):
    """
    Trả hồ sơ về bước trước.
    POST body JSON: { note: "lý do bắt buộc" }
    """
    record = get_object_or_404(
        RecordCompletion.objects.select_related("checkin_record", "company"),
        pk=completion_id,
    )

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        body = {}

    note = (body.get("note") or request.POST.get("note", "")).strip()

    try:
        record = return_step(record=record, actor=request.user, note=note)
    except ReturnStepError as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=400)

    advanceable = RecordCompletionPolicy.get_advanceable_steps(request.user)
    card_html   = render_to_string(
        "record_completion/staff/_card.html",
        {"completion": record, "advanceable_steps": advanceable},
        request=request,
    )
    return JsonResponse({
        "success":      True,
        "new_step":     record.current_step,
        "is_completed": False,
        "card_html":    card_html,
    })


@login_required(login_url="authentication:staff_login")
def log_timeline_view(request, completion_id: int):
    record, logs = get_completion_with_logs(completion_id)
    if not record:
        return JsonResponse({"success": False, "error": "Không tìm thấy."}, status=404)

    # Enrich mỗi log với step config và flag is_return
    enriched_logs = []
    for log_entry in logs:  # đã sắp theo confirmed_at tăng dần
        cfg = STEP_CONFIGS[log_entry.step] if log_entry.step < TOTAL_STEPS else COMPLETED_STAGE
        enriched_logs.append({
            "log":       log_entry,
            "config":    cfg,
            "is_return": log_entry.action == LOG_ACTION_RETURN,
        })

    html = render_to_string(
        "record_completion/staff/_log_timeline.html",
        {"record": record, "enriched_logs": enriched_logs},
        request=request,
    )
    return JsonResponse({"success": True, "html": html})
