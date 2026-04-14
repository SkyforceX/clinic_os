from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from apps.contract.models import ACTIVE_STATUSES, Contract
from apps.contract.policies import ContractPolicy
from apps.contract.services.implementation_plans import (
    build_package_rows,
    build_plan_log_entries,
    build_sheet_year,
    confirm_plan_row,
    export_plan_excel,
    get_or_create_plan,
    normalize_rows,
    unlock_plan_row,
    update_plan_rows_from_post,
)

APPROVER_SALES = "Sales Team"
APPROVER_OPERATIONS = "Operations Team"
APPROVER_ACCOUNTANTS = "Accountants"
APPROVER_NURSES = "Nurses"
APPROVER_DOCTORS = "Doctors"
APPROVER_CUSTOMER_SERVICE = "Customer Service Team"

APPROVER_LABELS = {
    APPROVER_SALES: "Phòng Kinh doanh",
    APPROVER_OPERATIONS: "Phòng Vận hành",
    APPROVER_ACCOUNTANTS: "Phòng Kế toán",
    APPROVER_NURSES: "Phòng Điều dưỡng",
    APPROVER_DOCTORS: "Giám đốc y khoa",
    APPROVER_CUSTOMER_SERVICE: "Phòng Chăm sóc khách hàng",
}

HEAD_APPROVER_GROUPS = [
    APPROVER_SALES,
    APPROVER_CUSTOMER_SERVICE,
    APPROVER_OPERATIONS,
    APPROVER_ACCOUNTANTS,
    APPROVER_NURSES,
]

ROW_APPROVER_MATRIX = {
    1: list(HEAD_APPROVER_GROUPS),
    2: list(HEAD_APPROVER_GROUPS),
    3: [APPROVER_ACCOUNTANTS],
    4: list(HEAD_APPROVER_GROUPS),
    5: [],
    6: [APPROVER_OPERATIONS, APPROVER_SALES, APPROVER_NURSES],
    7: [APPROVER_OPERATIONS, APPROVER_SALES, APPROVER_NURSES],
    8: list(HEAD_APPROVER_GROUPS),
    9: [APPROVER_OPERATIONS, APPROVER_ACCOUNTANTS],
    10: [APPROVER_OPERATIONS, APPROVER_ACCOUNTANTS],
    11: [APPROVER_OPERATIONS, APPROVER_ACCOUNTANTS],
    12: [APPROVER_OPERATIONS, APPROVER_ACCOUNTANTS],
    13: [APPROVER_OPERATIONS, APPROVER_SALES],
    14: [APPROVER_OPERATIONS],
    15: [APPROVER_OPERATIONS],
    16: [APPROVER_OPERATIONS],
    17: [APPROVER_NURSES, APPROVER_DOCTORS],
    18: [APPROVER_OPERATIONS, APPROVER_NURSES, APPROVER_DOCTORS],
    19: [APPROVER_NURSES, APPROVER_DOCTORS],
    20: [APPROVER_ACCOUNTANTS, APPROVER_SALES],
    21: [APPROVER_SALES, APPROVER_CUSTOMER_SERVICE],
}

APPROVER_ORDER = [
    APPROVER_SALES,
    APPROVER_CUSTOMER_SERVICE,
    APPROVER_OPERATIONS,
    APPROVER_ACCOUNTANTS,
    APPROVER_NURSES,
    APPROVER_DOCTORS,
]


def _implementation_contract_queryset():
    return (
        Contract.objects.select_related(
            "company",
            "created_by",
            "corporate_profile",
            "corporate_profile__quotation",
            "implementation_plan",
        )
        .prefetch_related(
            "service_lines",
            "blood_collection_schedules",
            "implementation_plan__logs",
        )
        .filter(
            corporate_profile__isnull=False,
            implementation_plan__is_published=True,
        )
        .filter(Q(is_locked=True) | Q(status__in=ACTIVE_STATUSES))
        .order_by("-approved_at", "-locked_at", "-updated_at", "-id")
    )


def _implementation_contract_for_edit_queryset():
    return (
        Contract.objects.select_related(
            "company",
            "created_by",
            "corporate_profile",
            "corporate_profile__quotation",
            "implementation_plan",
        )
        .prefetch_related(
            "service_lines",
            "blood_collection_schedules",
            "implementation_plan__logs",
        )
        .filter(corporate_profile__isnull=False)
        .order_by("-updated_at", "-id")
    )


def _get_contract_for_implementation(user, contract_id):
    contract = get_object_or_404(
        _implementation_contract_for_edit_queryset(),
        pk=contract_id,
    )

    if not ContractPolicy.can_view_implementation(user):
        raise Http404("Bạn không có quyền xem kế hoạch triển khai này.")

    return contract


def _get_user_approver_codes(user, contract):
    if not getattr(user, "is_authenticated", False):
        return set()

    if getattr(user, "is_superuser", False):
        return set(APPROVER_ORDER)

    codes = set()

    if (
        ContractPolicy.is_sales(user)
        and getattr(contract, "created_by_id", None) == getattr(user, "id", None)
    ):
        codes.add(APPROVER_SALES)

    if ContractPolicy.is_operations(user) and ContractPolicy.is_manager(user):
        codes.add(APPROVER_OPERATIONS)

    if ContractPolicy.is_accountant(user) and ContractPolicy.is_manager(user):
        codes.add(APPROVER_ACCOUNTANTS)

    if ContractPolicy.is_customer_service(user) and ContractPolicy.is_manager(user):
        codes.add(APPROVER_CUSTOMER_SERVICE)

    if ContractPolicy.is_nurse(user) and ContractPolicy.is_manager(user):
        codes.add(APPROVER_NURSES)

    if ContractPolicy.is_doctor(user) and ContractPolicy.is_manager(user):
        codes.add(APPROVER_DOCTORS)

    return codes


def _allowed_approver_codes_for_row(row_stt):
    try:
        row_stt = int(row_stt)
    except (TypeError, ValueError):
        return []
    return list(ROW_APPROVER_MATRIX.get(row_stt, []))


def _approver_label(code):
    return APPROVER_LABELS.get(code, code)


def _sync_plan_role_matrix(plan, contract):
    rows = normalize_rows(plan.rows_json or [], contract)
    changed = False

    for row in rows:
        desired_codes = _allowed_approver_codes_for_row(row.get("stt"))
        current_codes = list(row.get("department_keys") or [])
        current_confirmations = dict(row.get("confirmations") or {})

        filtered_confirmations = {
            key: value
            for key, value in current_confirmations.items()
            if key in desired_codes
        }

        if current_codes != desired_codes:
            row["department_keys"] = desired_codes
            changed = True

        if filtered_confirmations != current_confirmations:
            row["confirmations"] = filtered_confirmations
            changed = True

        is_locked = bool(filtered_confirmations)
        if bool(row.get("is_locked")) != is_locked:
            row["is_locked"] = is_locked
            changed = True

        if not filtered_confirmations:
            if row.get("locked_at") or row.get("locked_by_name"):
                row["locked_at"] = ""
                row["locked_by_name"] = ""
                changed = True

    if changed:
        plan.rows_json = rows
        plan.save(update_fields=["rows_json", "updated_at"])

    return plan


def _build_plan_rows_for_display(plan, contract, user, *, can_edit=False):
    rows = normalize_rows(plan.rows_json or [], contract)
    user_codes = _get_user_approver_codes(user, contract)

    can_view_all_confirmations = bool(
        getattr(user, "is_superuser", False)
        or can_edit
        or ContractPolicy.can_view_implementation_logs(user, contract)
    )

    display_rows = []
    for row in rows:
        confirmations = row.get("confirmations") or {}
        approver_codes = list(row.get("department_keys") or [])

        department_items = []
        for code in approver_codes:
            status = confirmations.get(code) or {}
            is_confirmed = bool(status.get("confirmed_at"))
            visible = can_view_all_confirmations or code in user_codes
            if not visible:
                continue

            department_items.append(
                {
                    "key": code,
                    "label": _approver_label(code),
                    "is_confirmed": is_confirmed,
                    "confirmed_at": status.get("confirmed_at", ""),
                    "confirmed_by_name": status.get("confirmed_by_name", ""),
                    "can_click": (code in user_codes) and not is_confirmed,
                }
            )

        display_rows.append(
            {
                **row,
                "is_locked": bool(confirmations),
                "is_editable": bool(can_edit and not confirmations),
                "department_items": department_items,
                "confirmed_count": sum(
                    1 for item in confirmations.values() if item.get("confirmed_at")
                ),
            }
        )

    return display_rows


def _can_user_confirm_department(user, contract, row_stt, department_key):
    if not getattr(user, "is_authenticated", False):
        return False

    if getattr(user, "is_superuser", False):
        return True

    allowed_codes = set(_allowed_approver_codes_for_row(row_stt))
    if department_key not in allowed_codes:
        return False

    user_codes = _get_user_approver_codes(user, contract)
    return department_key in user_codes


def _is_ajax_request(request):
    return request.headers.get("x-requested-with") == "XMLHttpRequest"


def _format_confirmed_at(value):
    if not value:
        return ""
    try:
        return value.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(value)


def _build_row_payload(plan, contract, user, row_stt, *, can_edit=False):
    rows = _build_plan_rows_for_display(
        plan,
        contract,
        user,
        can_edit=can_edit,
    )
    for row in rows:
        if str(row.get("stt")) == str(row_stt):
            return {
                "stt": row.get("stt"),
                "is_locked": bool(row.get("is_locked")),
                "is_editable": bool(row.get("is_editable")),
                "department_items": [
                    {
                        "key": item.get("key"),
                        "label": item.get("label"),
                        "is_confirmed": bool(item.get("is_confirmed")),
                        "confirmed_by_name": item.get("confirmed_by_name") or "",
                        "confirmed_at": _format_confirmed_at(item.get("confirmed_at")),
                        "can_click": bool(item.get("can_click")),
                    }
                    for item in (row.get("department_items") or [])
                ],
            }
    return None


@login_required(login_url="authentication:staff_login")
@require_GET
def implementation_plan_list(request):
    if not ContractPolicy.can_view_implementation(request.user):
        raise Http404("Bạn không có quyền xem danh sách triển khai.")

    query = (request.GET.get("q") or "").strip()
    contracts = _implementation_contract_queryset()

    if query:
        contracts = contracts.filter(
            Q(contract_number__icontains=query)
            | Q(company__name__icontains=query)
            | Q(contact_person__icontains=query)
            | Q(corporate_profile__company_name_snapshot__icontains=query)
        )

    items = []
    for contract in contracts:
        plan = getattr(contract, "implementation_plan", None)
        items.append(
            {
                "contract": contract,
                "plan": plan,
                "can_view_contract_link": ContractPolicy.can_view_implementation_contract_link(
                    request.user,
                    contract,
                ),
                "can_edit_plan": ContractPolicy.can_edit_implementation(
                    request.user,
                    contract,
                ),
            }
        )

    context = {
        "items": items,
        "query": query,
        "total_items": len(items),
    }
    return render(
        request,
        "contract/staff/implementation_plan_list.html",
        context,
    )


@login_required(login_url="authentication:staff_login")
@require_http_methods(["GET", "POST"])
def implementation_plan_detail(request, contract_id):
    contract = _get_contract_for_implementation(request.user, contract_id)
    plan = get_or_create_plan(contract)
    plan = _sync_plan_role_matrix(plan, contract)

    can_edit = ContractPolicy.can_edit_implementation(request.user, contract)
    can_view_contract_link = ContractPolicy.can_view_implementation_contract_link(
        request.user,
        contract,
    )
    can_view_logs = ContractPolicy.can_view_implementation_logs(request.user, contract)
    can_manage_unlock = ContractPolicy.can_manage_implementation_unlock(request.user, contract)

    if request.method == "POST":
        action = (request.POST.get("action") or "save").strip()
        row_stt = request.POST.get("row_stt")
        department_key = (request.POST.get("department_key") or "").strip()

        try:
            if action == "save_draft":
                if not can_edit:
                    if _is_ajax_request(request):
                        return JsonResponse(
                            {"ok": False, "message": "Bạn không có quyền cập nhật kế hoạch triển khai."},
                            status=403,
                        )
                    messages.error(request, "Bạn không có quyền cập nhật kế hoạch triển khai.")
                else:
                    update_plan_rows_from_post(plan, request.POST, contract, actor=request.user)
                    msg = "Đã lưu nháp." if plan.is_published else "Đã lưu nháp. Kế hoạch chưa công khai."

                    if _is_ajax_request(request):
                        return JsonResponse({"ok": True, "message": msg})

                    messages.success(request, msg)

            elif action == "save":
                if not can_edit:
                    if _is_ajax_request(request):
                        return JsonResponse(
                            {"ok": False, "message": "Bạn không có quyền cập nhật kế hoạch triển khai."},
                            status=403,
                        )
                    messages.error(request, "Bạn không có quyền cập nhật kế hoạch triển khai.")
                else:
                    update_plan_rows_from_post(plan, request.POST, contract, actor=request.user)
                    if not plan.is_published:
                        plan.is_published = True
                        plan.save(update_fields=["is_published", "updated_at"])

                    msg = "Đã lưu và công khai kế hoạch triển khai."

                    if _is_ajax_request(request):
                        return JsonResponse({"ok": True, "message": msg})

                    messages.success(request, msg)

            elif action == "confirm":
                if not _can_user_confirm_department(
                    request.user,
                    contract,
                    row_stt,
                    department_key,
                ):
                    message = "Bạn không có quyền xác nhận ở dòng / vai trò này."
                    if _is_ajax_request(request):
                        return JsonResponse({"ok": False, "message": message}, status=403)
                    messages.error(request, message)
                else:
                    changed, row = confirm_plan_row(
                        plan,
                        contract,
                        row_stt=row_stt,
                        department_key=department_key,
                        actor=request.user,
                    )

                    message = (
                        f"Đã xác nhận dòng {row.get('stt')} - {row.get('category')} cho {_approver_label(department_key)}."
                        if changed
                        else "Dòng này đã được xác nhận trước đó."
                    )

                    if _is_ajax_request(request):
                        row_payload = _build_row_payload(
                            plan,
                            contract,
                            request.user,
                            row_stt=row_stt,
                            can_edit=can_edit,
                        )
                        return JsonResponse(
                            {
                                "ok": True,
                                "changed": changed,
                                "message": message,
                                "row": row_payload,
                            }
                        )

                    if changed:
                        messages.success(request, message)
                    else:
                        messages.info(request, message)

            elif action == "unlock":
                if not can_manage_unlock:
                    message = "Bạn không có quyền gỡ xác nhận / mở khóa dòng này."
                    if _is_ajax_request(request):
                        return JsonResponse({"ok": False, "message": message}, status=403)
                    messages.error(request, message)
                else:
                    changed, row = unlock_plan_row(
                        plan,
                        contract,
                        row_stt=row_stt,
                        actor=request.user,
                    )

                    message = (
                        f"Đã gỡ xác nhận và mở khóa dòng {row.get('stt')} - {row.get('category')}."
                        if changed
                        else "Dòng này chưa có xác nhận để gỡ."
                    )

                    if _is_ajax_request(request):
                        row_payload = _build_row_payload(
                            plan,
                            contract,
                            request.user,
                            row_stt=row_stt,
                            can_edit=can_edit,
                        )
                        return JsonResponse(
                            {
                                "ok": True,
                                "changed": changed,
                                "message": message,
                                "row": row_payload,
                            }
                        )

                    if changed:
                        messages.success(request, message)
                    else:
                        messages.info(request, message)

            else:
                if _is_ajax_request(request):
                    return JsonResponse({"ok": False, "message": "Thao tác không hợp lệ."}, status=400)
                messages.error(request, "Thao tác không hợp lệ.")

        except ValueError as exc:
            if _is_ajax_request(request):
                return JsonResponse({"ok": False, "message": str(exc)}, status=400)
            messages.error(request, str(exc))

        return redirect("contract:implementation_plan_detail", contract_id=contract.id)

    profile = getattr(contract, "corporate_profile", None)
    package_rows = build_package_rows(contract)

    company_name = ""
    if profile and getattr(profile, "company_name_snapshot", None):
        company_name = profile.company_name_snapshot
    elif contract.company:
        company_name = contract.company.name

    plan_rows = _build_plan_rows_for_display(
        plan,
        contract,
        request.user,
        can_edit=can_edit,
    )

    log_entries = []
    if can_view_logs:
        log_entries = build_plan_log_entries(plan.logs.select_related("actor").all())

    context = {
        "contract": contract,
        "profile": profile,
        "plan": plan,
        "plan_rows": plan_rows,
        "package_rows": package_rows,
        "plan_year": build_sheet_year(contract),
        "company_name": company_name,
        "can_edit_plan": can_edit,
        "can_view_contract_link": can_view_contract_link,
        "can_view_logs": can_view_logs,
        "can_manage_unlock": can_manage_unlock,
        "is_executive": ContractPolicy.is_executive(request.user),
        "log_entries": log_entries,
    }
    return render(request, "contract/staff/corporate_implementation_plan.html", context)


@login_required(login_url="authentication:staff_login")
@require_GET
def implementation_plan_export_excel(request, contract_id):
    contract = _get_contract_for_implementation(request.user, contract_id)
    plan = get_or_create_plan(contract)
    plan = _sync_plan_role_matrix(plan, contract)

    output, filename = export_plan_excel(contract, plan)
    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response