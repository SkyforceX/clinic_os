"""
apps/reception/views.py
========================
Views cho cÃƒÂ´ng cÃ¡Â»Â¥ check-in / check-out tÃ¡ÂºÂ¡i quÃ¡ÂºÂ§y lÃ¡Â»â€¦ tÃƒÂ¢n.

XÃƒÂ¡c thÃ¡Â»Â±c riÃƒÂªng (session key "reception_operator_id"),
KHÃƒâ€NG dÃƒÂ¹ng @login_required cÃ¡Â»Â§a staff Ã¢â‚¬â€ trÃƒÂ¡nh lÃ¡Â»â„¢ dÃ¡Â»Â¯ liÃ¡Â»â€¡u nÃ¡Â»â„¢i bÃ¡Â»â„¢.
"""

import json
import logging
from datetime import date

from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from apps.reception.models import CheckInStatus
from apps.reception.policies import ReceptionPolicy
from apps.reception.selectors.checkin_selectors import (
    get_checkin_record_company_name,
    get_recent_checkins,
    get_today_stats,
)
from apps.reception.services.checkin_service import (
    authenticate_operator,
    do_checkin,
    do_checkout,
    do_defer,
    lookup_patient,
)

User = get_user_model()
logger = logging.getLogger(__name__)


def get_operator(request):
    """LÃ¡ÂºÂ¥y user operator tÃ¡Â»Â« session check-in."""
    uid = ReceptionPolicy.get_operator_id_from_session(request)
    if not uid:
        return None
    try:
        return User.objects.get(pk=uid)
    except User.DoesNotExist:
        ReceptionPolicy.clear_session(request)
        return None


# Ã¢â€â‚¬Ã¢â€â‚¬ Trang chÃƒÂ­nh (GET: form login hoÃ¡ÂºÂ·c tool, POST: xÃ¡Â»Â­ lÃƒÂ½ login) Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

@ensure_csrf_cookie
@csrf_protect
def checkin_tool(request):
    """
    Trang check-in chÃƒÂ­nh.
    - NÃ¡ÂºÂ¿u chÃ†Â°a xÃƒÂ¡c thÃ¡Â»Â±c session Ã¢â€ â€™ hiÃ¡Â»â€¡n mini login form.
    - NÃ¡ÂºÂ¿u Ã„â€˜ÃƒÂ£ xÃƒÂ¡c thÃ¡Â»Â±c Ã¢â€ â€™ hiÃ¡Â»â€¡n tool Ã„â€˜Ã¡ÂºÂ§y Ã„â€˜Ã¡Â»Â§.
    """
    operator = get_operator(request)

    if request.method == "POST" and "operator_login" in request.POST:
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user, err = authenticate_operator(username, password)
        if user:
            ReceptionPolicy.set_session(request, user.pk)
            return redirect("reception:checkin_tool")
        return render(request, "reception/checkin_tool.html", {
            "operator": None,
            "login_error": err,
            "today": date.today(),
        })

    if request.method == "POST" and "operator_logout" in request.POST:
        ReceptionPolicy.clear_session(request)
        return redirect("reception:checkin_tool")

    today = date.today()
    company_stats, total_today, exam_date = get_today_stats(today)
    recent = get_recent_checkins(today, limit=30)

    return render(request, "reception/checkin_tool.html", {
        "operator": operator,
        "today": today,
        "company_stats": company_stats,
        "total_today": total_today,
        "recent": recent,
        "CheckInStatus": CheckInStatus,
    })


def _build_existing_record_payload(existing):
    existing_data = None
    if existing:
        checkin_time = ""
        if existing.checked_in_at:
            import pytz

            local_tz = pytz.timezone("Asia/Ho_Chi_Minh")
            checkin_time = existing.checked_in_at.astimezone(local_tz).strftime("%H:%M")
        existing_data = {
            "id": existing.pk,
            "status": existing.status,
            "status_label": existing.get_status_display(),
            "checkin_time": checkin_time,
            "note": existing.note,
            "exam_date": existing.exam_date.strftime("%d/%m/%Y") if existing.exam_date else "",
        }
    return existing_data


# Ã¢â€â‚¬Ã¢â€â‚¬ AJAX: tra cÃ¡Â»Â©u bÃ¡Â»â€¡nh nhÃƒÂ¢n Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

@csrf_protect
def ajax_lookup(request):
    """
    POST { ma_bn: str }
    Ã¢â€ â€™ { ok, patient: {...}, existing_record: {...}|null, error }
    """
    operator = get_operator(request)
    if not operator:
        return JsonResponse({"ok": False, "error": "PhiÃƒÂªn lÃƒÂ m viÃ¡Â»â€¡c hÃ¡ÂºÂ¿t hÃ¡ÂºÂ¡n. Vui lÃƒÂ²ng Ã„â€˜Ã„Æ’ng nhÃ¡ÂºÂ­p lÃ¡ÂºÂ¡i."}, status=401)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({"ok": False, "error": "DÃ¡Â»Â¯ liÃ¡Â»â€¡u khÃƒÂ´ng hÃ¡Â»Â£p lÃ¡Â»â€¡."}, status=400)

    ma_bn = (body.get("ma_bn") or "").strip().upper()
    if not ma_bn:
        return JsonResponse({"ok": False, "error": "Vui lÃƒÂ²ng nhÃ¡ÂºÂ­p mÃƒÂ£ bÃ¡Â»â€¡nh nhÃƒÂ¢n."})

    try:
        today = date.today()
        result, err = lookup_patient(ma_bn, today)
        if err:
            return JsonResponse({"ok": False, "error": err})

        patient = result["patient"]
        existing = result["existing_record"]

        ngay_sinh_str = ""
        if patient.ngay_sinh:
            ngay_sinh_str = patient.ngay_sinh.strftime("%d/%m/%Y")

        exam_range = ""
        if result["exam_start"] and result["exam_end"]:
            exam_range = f"{result['exam_start'].strftime('%d/%m/%Y')} Ã¢â‚¬â€œ {result['exam_end'].strftime('%d/%m/%Y')}"
        elif result["exam_start"]:
            exam_range = f"TÃ¡Â»Â« {result['exam_start'].strftime('%d/%m/%Y')}"

        gioi_tinh_display = {"Nam": "Nam", "NÃ¡Â»Â¯": "NÃ¡Â»Â¯", "MALE": "Nam", "FEMALE": "NÃ¡Â»Â¯"}.get(
            patient.gioi_tinh, patient.gioi_tinh or ""
        )

        return JsonResponse({
            "ok": True,
            "patient": {
                "ma_bn": patient.ma_bn,
                "ho_ten": patient.ho_ten,
                "gioi_tinh": gioi_tinh_display,
                "ngay_sinh": ngay_sinh_str,
                "company_name": result["company_name"],
                "exam_range": exam_range,
            },
            "existing_record": _build_existing_record_payload(existing),
            "already_checked_in": result["already_checked_in"],
            "already_checked_out": result["already_checked_out"],
            "is_deferred": result["is_deferred"],
            "contract_done": result["contract_done"],
        })
    except Exception as exc:
        logger.exception("Reception ajax_lookup failed for ma_bn=%s", ma_bn)
        return JsonResponse({
            "ok": False,
            "error": f"Lá»—i tra cá»©u mÃ¡y chá»§ [{exc.__class__.__name__}]: {exc}",
        }, status=500)


# Ã¢â€â‚¬Ã¢â€â‚¬ AJAX: thÃ¡Â»Â±c hiÃ¡Â»â€¡n action (check-in / check-out / defer) Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

@csrf_protect
@require_POST
def ajax_action(request):
    """
    POST { action: "checkin"|"checkout"|"defer", ma_bn, record_id, note }
    Ã¢â€ â€™ { ok, message, status, status_label, stats }
    """
    operator = get_operator(request)
    if not operator:
        return JsonResponse({"ok": False, "error": "PhiÃƒÂªn lÃƒÂ m viÃ¡Â»â€¡c hÃ¡ÂºÂ¿t hÃ¡ÂºÂ¡n."}, status=401)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({"ok": False, "error": "DÃ¡Â»Â¯ liÃ¡Â»â€¡u khÃƒÂ´ng hÃ¡Â»Â£p lÃ¡Â»â€¡."}, status=400)

    action = body.get("action", "")
    ma_bn = (body.get("ma_bn") or "").strip().upper()
    record_id = body.get("record_id")
    note = (body.get("note") or "").strip()
    today = date.today()

    try:
        if action == "checkin":
            record, err = do_checkin(ma_bn, note, operator, today)
            if err:
                return JsonResponse({"ok": False, "error": err})
            msg = f"Check-in thành công: {record.snapshot_ho_ten}"

        elif action == "checkout":
            if not record_id:
                return JsonResponse({"ok": False, "error": "ThiÃ¡ÂºÂ¿u record_id."})
            record, err = do_checkout(int(record_id), note, operator)
            if err:
                return JsonResponse({"ok": False, "error": err})
            msg = f"Check-out thành công: {record.snapshot_ho_ten}"

        elif action == "defer":
            if not record_id:
                return JsonResponse({"ok": False, "error": "ThiÃ¡ÂºÂ¿u record_id."})
            record, err = do_defer(int(record_id), note, operator)
            if err:
                return JsonResponse({"ok": False, "error": err})
            msg = f"?? ??nh d?u quay l?i sau: {record.snapshot_ho_ten}"

        else:
            return JsonResponse({"ok": False, "error": "Action khÃƒÂ´ng hÃ¡Â»Â£p lÃ¡Â»â€¡."}, status=400)

        company_stats, total_today, _ = get_today_stats(today)
        stats_data = [
            {
                "company_name": s["company_name"],
                "exam_start": s["exam_start"].strftime("%d/%m/%Y") if s["exam_start"] else "",
                "exam_end": s["exam_end"].strftime("%d/%m/%Y") if s["exam_end"] else "",
                "total_checkin": s["total_checkin"],
                "total_checkout": s["total_checkout"],
                "total_deferred": s["total_deferred"],
                "total_all": s["total_checkin"] + s["total_checkout"] + s["total_deferred"],
            }
            for s in company_stats
        ]

        return JsonResponse({
            "ok": True,
            "message": msg,
            "status": record.status,
            "status_label": record.get_status_display(),
            "record_id": record.pk,
            "stats": stats_data,
            "total_today": total_today,
        })
    except Exception as exc:
        logger.exception(
            "Reception ajax_action failed: action=%s ma_bn=%s record_id=%s",
            action,
            ma_bn,
            record_id,
        )
        return JsonResponse({
            "ok": False,
            "error": f"Lá»—i xá»­ lÃ½ mÃ¡y chá»§ [{exc.__class__.__name__}]: {exc}",
        }, status=500)


# Ã¢â€â‚¬Ã¢â€â‚¬ AJAX: refresh stats panel Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

def ajax_stats(request):
    """GET Ã¢â€ â€™ JSON stats panel data Ã„â€˜Ã¡Â»Æ’ auto-refresh."""
    operator = get_operator(request)
    if not operator:
        return JsonResponse({"ok": False, "error": "ChÃ†Â°a xÃƒÂ¡c thÃ¡Â»Â±c."}, status=401)

    today = date.today()
    company_stats, total_today, _ = get_today_stats(today)

    recent_records = get_recent_checkins(today, limit=30)
    recent_data = []
    import pytz

    local_tz = pytz.timezone("Asia/Ho_Chi_Minh")
    for rec in recent_records:
        t = ""
        if rec.checked_in_at:
            t = rec.checked_in_at.astimezone(local_tz).strftime("%H:%M")
        recent_data.append({
            "ma_bn": rec.snapshot_ma_bn,
            "ho_ten": rec.snapshot_ho_ten,
            "company_name": get_checkin_record_company_name(rec),
            "status": rec.status,
            "status_label": rec.get_status_display(),
            "time": t,
        })

    stats_data = [
        {
            "company_name": s["company_name"],
            "exam_start": s["exam_start"].strftime("%d/%m/%Y") if s["exam_start"] else "",
            "exam_end": s["exam_end"].strftime("%d/%m/%Y") if s["exam_end"] else "",
            "total_checkin": s["total_checkin"],
            "total_checkout": s["total_checkout"],
            "total_deferred": s["total_deferred"],
            "total_all": s["total_checkin"] + s["total_checkout"] + s["total_deferred"],
        }
        for s in company_stats
    ]

    return JsonResponse({
        "ok": True,
        "stats": stats_data,
        "recent": recent_data,
        "total_today": total_today,
    })


# ── AJAX: lịch sử check-in (có filter) ──────────────────────────────────────

def ajax_history(request):
    """GET ?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD&ma_bn=&ho_ten= → JSON records."""
    operator = get_operator(request)
    if not operator:
        return JsonResponse({"ok": False, "error": "Chưa xác thực."}, status=401)

    from datetime import datetime as _dt
    import pytz as _pytz

    date_from_str = request.GET.get("date_from", "").strip()
    date_to_str   = request.GET.get("date_to",   "").strip()
    ma_bn_q       = request.GET.get("ma_bn",  "").strip().upper()
    ho_ten_q      = request.GET.get("ho_ten", "").strip()

    try:
        date_from = _dt.strptime(date_from_str, "%Y-%m-%d").date() if date_from_str else date.today()
        date_to   = _dt.strptime(date_to_str,   "%Y-%m-%d").date() if date_to_str   else date.today()
    except ValueError:
        return JsonResponse({"ok": False, "error": "Định dạng ngày không hợp lệ."}, status=400)

    from apps.reception.models import CheckInRecord
    qs = (
        CheckInRecord.objects
        .filter(exam_date__range=(date_from, date_to))
        .select_related("operator")
        .order_by("-exam_date", "-checked_in_at")
    )
    if ma_bn_q:
        qs = qs.filter(snapshot_ma_bn__icontains=ma_bn_q)
    if ho_ten_q:
        qs = qs.filter(snapshot_ho_ten__icontains=ho_ten_q)

    local_tz = _pytz.timezone("Asia/Ho_Chi_Minh")
    records = []
    for rec in qs[:300]:
        t = ""
        if rec.checked_in_at:
            t = rec.checked_in_at.astimezone(local_tz).strftime("%H:%M")
        op_name = ""
        if rec.operator:
            op_name = rec.operator.get_full_name() or rec.operator.username
        records.append({
            "ma_bn":        rec.snapshot_ma_bn,
            "ho_ten":       rec.snapshot_ho_ten,
            "company_name": get_checkin_record_company_name(rec),
            "status":       rec.status,
            "checkin_time": t,
            "exam_date":    rec.exam_date.strftime("%d/%m/%Y") if rec.exam_date else "",
            "operator":     op_name,
            "note":         rec.note or "",
        })

    return JsonResponse({"ok": True, "records": records})


# ── AJAX: danh sách đăng ký khám đoàn hôm nay ──────────────────────────────

def ajax_today_registrations(request):
    """GET → JSON danh sách Appointment của hôm nay (slot type CONTRACT)."""
    operator = get_operator(request)
    if not operator:
        return JsonResponse({"ok": False, "error": "Chưa xác thực."}, status=401)

    from apps.booking.models import Appointment, AppointmentStatus
    from apps.his_integration.selectors import list_active_schedule_configs_for_his_patient
    from apps.scheduling.models import SlotType

    today = date.today()
    company_name_cache = {}

    def resolve_his_company_name_for_patient(*, patient_code):
        normalized_code = (patient_code or "").strip().upper()
        if not normalized_code:
            return ""
        if normalized_code in company_name_cache:
            return company_name_cache[normalized_code]

        schedule_config = (
            list_active_schedule_configs_for_his_patient(patient_code=normalized_code)
            .filter(exam_start_date__lte=today, exam_end_date__gte=today)
            .first()
        )
        his_package = getattr(schedule_config, "his_package", None) if schedule_config else None
        company_name = (
            getattr(his_package, "company_name", "")
            or getattr(getattr(his_package, "organization", None), "name", "")
        )
        company_name_cache[normalized_code] = company_name or ""
        return company_name_cache[normalized_code]

    qs = (
        Appointment.objects
        .filter(
            schedule_slot__date=today,
            schedule_slot__slot_type=SlotType.CONTRACT,
        )
        .exclude(status=AppointmentStatus.CANCELLED)
        .select_related(
            "patient",
            "patient__company",
            "his_patient_sync",
            "schedule_slot",
            "schedule_slot__contract",
            "schedule_slot__contract__company",
            "schedule_slot__quotation",
        )
        .order_by("schedule_slot__shift", "his_patient_sync__full_name", "patient__ho_ten")
    )

    status_labels = {s.value: s.label for s in AppointmentStatus}
    shift_labels  = {"AM": "Sáng", "PM": "Chiều"}

    rows = []
    for appt in qs:
        slot = appt.schedule_slot

        # Thông tin BN
        if appt.his_patient_sync:
            his = appt.his_patient_sync
            ma_bn    = his.his_patient_code or ""
            ho_ten   = his.full_name or ""
            gender_map = {"NAM": "Nam", "NU": "Nữ", "M": "Nam", "F": "Nữ", "0": "Nam", "1": "Nữ"}
            gioi_tinh = gender_map.get((his.gender_code or "").upper(), his.gender_code or "")
            if his.birth_date_text:
                ngay_sinh = his.birth_date_text
            elif his.birth_year:
                ngay_sinh = str(his.birth_year)
            else:
                ngay_sinh = ""
        elif appt.patient:
            pt = appt.patient
            ma_bn     = pt.ma_bn or ""
            ho_ten    = pt.ho_ten or ""
            gioi_tinh = pt.gioi_tinh or ""
            ngay_sinh = pt.ngay_sinh.strftime("%d/%m/%Y") if pt.ngay_sinh else ""
        else:
            ma_bn = ho_ten = gioi_tinh = ngay_sinh = ""

        # Tên công ty: chỉ lấy từ his_integration
        company_name = resolve_his_company_name_for_patient(patient_code=ma_bn)

        rows.append({
            "ma_bn":        ma_bn,
            "ho_ten":       ho_ten,
            "gioi_tinh":    gioi_tinh,
            "ngay_sinh":    ngay_sinh,
            "company_name": company_name,
            "shift":        slot.shift,
            "shift_label":  shift_labels.get(slot.shift, slot.shift),
            "status":       appt.status,
            "status_label": status_labels.get(appt.status, appt.status),
        })

    return JsonResponse({
        "ok":    True,
        "date":  today.strftime("%d/%m/%Y"),
        "rows":  rows,
        "total": len(rows),
    })
