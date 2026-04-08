import json

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.engagement.models import CallLog, Contact, ContactList
from apps.engagement.policies import EngagementPolicy
from apps.engagement.services.contact_service import (
    assign_contacts_to_agent,
    import_contacts_from_excel,
    log_call,
)

User = get_user_model()


def _deny_agent(request):
    if not EngagementPolicy.is_agent(request.user):
        return HttpResponseForbidden()
    return None


# ── Contact List ───────────────────────────────────────────────────────────────

@login_required(login_url="authentication:staff_login")
def contact_list_index(request):
    denied = _deny_agent(request)
    if denied:
        return denied

    lists = ContactList.objects.select_related("created_by","assigned_to").order_by("-created_at")
    if not EngagementPolicy.is_engagement_admin(request.user):
        # Agent chỉ thấy list được giao cho mình
        lists = lists.filter(assigned_to=request.user)

    return render(request, "engagement/staff/contact_list_index.html", {
        "contact_lists":  lists,
        "can_upload":     EngagementPolicy.can_upload_list(request.user),
        "is_engagement_admin":  EngagementPolicy.is_engagement_admin(request.user),
    })


@login_required(login_url="authentication:staff_login")
def contact_list_create(request):
    if not EngagementPolicy.can_upload_list(request.user):
        return HttpResponseForbidden()

    if request.method == "POST":
        p = request.POST
        name = (p.get("name") or "").strip()
        if not name:
            messages.error(request, "Vui lòng nhập tên danh sách.")
            return redirect("engagement:contact_list_create")

        allowed_groups = [g.strip() for g in p.get("allow_full_phone_groups","").split(",") if g.strip()]
        clist = ContactList.objects.create(
            name=name,
            description=p.get("description",""),
            campaign_tag=p.get("campaign_tag",""),
            allow_full_phone_groups=allowed_groups,
            assigned_to_id=p.get("assigned_to_id") or None,
            created_by=request.user,
        )
        # Upload file nếu có
        file_obj = request.FILES.get("excel_file")
        if file_obj:
            try:
                result = import_contacts_from_excel(
                    actor=request.user,
                    contact_list=clist,
                    file_obj=file_obj,
                )
                messages.success(request, f"✅ Đã import {result['created']} liên hệ.")
                for e in result["errors"][:5]:
                    messages.warning(request, e)
            except Exception as exc:
                messages.error(request, f"Lỗi import: {exc}")
        else:
            messages.success(request, f"Đã tạo danh sách '{clist.name}'.")

        return redirect("engagement:contact_list_detail", list_id=clist.pk)

    agents = list(
        User.objects.filter(
            groups__name__in=["Engagement Agent","Engagement Team","Engagement Lead","Manager","Managers"]
        ).distinct().order_by("first_name","username")
    )
    return render(request, "engagement/staff/contact_list_create.html", {"agents": agents})


@login_required(login_url="authentication:staff_login")
def contact_list_detail(request, list_id):
    denied = _deny_agent(request)
    if denied:
        return denied

    clist = get_object_or_404(ContactList, pk=list_id)
    is_admin = EngagementPolicy.is_engagement_admin(request.user)
    can_view_phone = EngagementPolicy.can_view_full_phone(request.user, clist)

    # Filter
    status_filter = request.GET.get("status") or ""
    assigned_filter = request.GET.get("assigned") or ""
    search = request.GET.get("q") or ""

    contacts_qs = clist.contacts.select_related("assigned_to")
    if status_filter:
        contacts_qs = contacts_qs.filter(status=status_filter)
    if assigned_filter == "me":
        contacts_qs = contacts_qs.filter(assigned_to=request.user)
    elif assigned_filter == "unassigned":
        contacts_qs = contacts_qs.filter(assigned_to__isnull=True)
    if search:
        from django.db.models import Q
        contacts_qs = contacts_qs.filter(
            Q(full_name__icontains=search) | Q(company_name__icontains=search)
        )
    if not is_admin:
        contacts_qs = contacts_qs.filter(assigned_to=request.user)

    agents = []
    if is_admin:
        agents = list(User.objects.filter(
            groups__name__in=["Engagement Agent","Engagement Team","Engagement Lead"]
        ).distinct().order_by("first_name","username"))

    return render(request, "engagement/staff/contact_list_detail.html", {
        "clist":          clist,
        "contacts":       contacts_qs[:200],
        "can_view_phone": can_view_phone,
        "is_admin":       is_admin,
        "agents":         agents,
        "status_filter":  status_filter,
        "search":         search,
        "status_choices": Contact.Status.choices,
        "outcome_choices": CallLog.Outcome.choices,
        "call_channel_choices": CallLog.Channel.choices,
    })


# ── Contact detail + call log ──────────────────────────────────────────────────

@login_required(login_url="authentication:staff_login")
def contact_detail(request, contact_id):
    denied = _deny_agent(request)
    if denied:
        return denied

    contact  = get_object_or_404(Contact.objects.select_related("contact_list","assigned_to","linked_company"), pk=contact_id)
    can_view = EngagementPolicy.can_view_full_phone(request.user, contact.contact_list)
    is_admin = EngagementPolicy.is_engagement_admin(request.user)

    if not is_admin and contact.assigned_to_id != request.user.id:
        return HttpResponseForbidden()

    call_logs = contact.call_logs.select_related("agent").order_by("-called_at")

    return render(request, "engagement/staff/contact_detail.html", {
        "contact":   contact,
        "phone":     contact.phone_for_user(request.user),
        "can_view_phone": can_view,
        "call_logs": call_logs,
        "outcome_choices": CallLog.Outcome.choices,
        "call_channel_choices": CallLog.Channel.choices,
        "status_choices": Contact.Status.choices,
    })


# ── AJAX: log call ─────────────────────────────────────────────────────────────

@login_required(login_url="authentication:staff_login")
@require_POST
def ajax_log_call(request, contact_id):
    denied = _deny_agent(request)
    if denied:
        return denied

    body = json.loads(request.body)
    try:
        from django.utils.dateparse import parse_datetime
        follow_up_raw = body.get("follow_up_at")
        follow_up = parse_datetime(follow_up_raw) if follow_up_raw else None

        log_call(
            agent=request.user,
            contact_id=contact_id,
            outcome=body.get("outcome","NO_ANSWER"),
            channel=body.get("channel","PHONE"),
            duration_s=int(body.get("duration_s",0)),
            note=body.get("note",""),
            follow_up_at=follow_up,
        )
        return JsonResponse({"ok": True})
    except Exception as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)


# ── AJAX: assign contacts ──────────────────────────────────────────────────────

@login_required(login_url="authentication:staff_login")
@require_POST
def ajax_assign(request):
    if not EngagementPolicy.can_assign_contacts(request.user):
        return JsonResponse({"ok": False, "error": "Không có quyền"}, status=403)
    body = json.loads(request.body)
    contact_ids = body.get("contact_ids", [])
    agent_id    = body.get("agent_id") or None
    count = assign_contacts_to_agent(actor=request.user, contact_ids=contact_ids, agent_id=agent_id)
    return JsonResponse({"ok": True, "count": count})


# ── AJAX: upload Excel vào list đã có ─────────────────────────────────────────

@login_required(login_url="authentication:staff_login")
@require_POST
def ajax_upload_excel(request, list_id):
    if not EngagementPolicy.can_upload_list(request.user):
        return JsonResponse({"ok": False, "error": "Không có quyền"}, status=403)
    clist    = get_object_or_404(ContactList, pk=list_id)
    file_obj = request.FILES.get("excel_file")
    if not file_obj:
        return JsonResponse({"ok": False, "error": "Không có file"}, status=400)
    try:
        overwrite = request.POST.get("overwrite") == "1"
        result = import_contacts_from_excel(
            actor=request.user,
            contact_list=clist,
            file_obj=file_obj,
            overwrite=overwrite,
        )
        return JsonResponse({"ok": True, **result})
    except Exception as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
