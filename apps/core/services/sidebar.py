from __future__ import annotations

from typing import Any, Dict, List, Optional

from django.urls import NoReverseMatch, reverse


def _is_supperuser(user) -> bool:
    return getattr(user, "is_superuser", True) or user.groups.filter(
        name__in=["Superuser", "Admin", "Admins"]
    ).exists()


def _is_manager(user) -> bool:
    return getattr(user, "is_superuser", False) or user.groups.filter(
        name__in=["Manager", "Managers", "Medical Director"]
    ).exists()


def _is_sales(user) -> bool:
    return user.groups.filter(name__in=["Sales Team", "Sales"]).exists()


def _is_doctor(user) -> bool:
    return user.groups.filter(name__in=["Doctor", "Doctors"]).exists()


def _is_hr_admin(user) -> bool:
    return getattr(user, "is_superuser", False) or user.groups.filter(
        name__in=["HR Admin", "HR"]
    ).exists()


def _is_executive(user) -> bool:
    return getattr(user, "is_superuser", False) or user.groups.filter(
        name__in=["Executive", "Executives"]
    ).exists()


def _can_view_record_completion(user) -> bool:
    return getattr(user, "is_superuser", False) or user.groups.filter(
        name__in=[
            "Executive",
            "Executives",
            "Medical Director",
            "Director",
            "Manager",
            "Managers",
            "Operations Team",
            "Operations",
            "VH",
            "Vận hành",
            "Van hanh",
            "Nurses",
            "Nursing",
            "Điều dưỡng",
            "Dieu duong",
            "DD",
            "ĐD",
        ]
    ).exists()


def _is_it_admin(user) -> bool:
    return getattr(user, "is_superuser", False) or user.groups.filter(
        name__in=["IT Admin", "IT", "IT Support"]
    ).exists()


def _is_care(user) -> bool:
    return (
        getattr(user, "is_superuser", False)
        or user.groups.filter(
            name__in=[
                "Care Agent",
                "Care Team",
                "Care Lead",
                "Care Admin",
                "Manager",
                "Managers",
                "Sales Team",
                "Sales",
            ]
        ).exists()
    )


def _is_meeting_participant(user) -> bool:
    return bool(user and user.is_authenticated)


def _can_use_tasks(user) -> bool:
    return bool(user and user.is_authenticated)


def _can_create_task(user) -> bool:
    try:
        from apps.tasks.policies import TaskPolicy
        return TaskPolicy.can_create_task(user)
    except Exception:
        return _is_executive(user) or _is_hr_admin(user) or _is_manager(user)


def _can_use_helpdesk(user) -> bool:
    """Executive gửi ticket; IT Admin xử lý ticket."""
    return bool(user and user.is_authenticated) and (
        _is_executive(user) or _is_it_admin(user) or _is_manager(user)
    )


def _safe_reverse(url_name: str) -> Optional[str]:
    try:
        return reverse(url_name)
    except NoReverseMatch:
        return None


def _current_route_state(request):
    resolver_match = getattr(request, "resolver_match", None)
    current_url_name = getattr(resolver_match, "url_name", "") or ""
    current_app_name = getattr(resolver_match, "app_name", "") or ""
    return current_url_name, current_app_name


def _item(
    *,
    request,
    label: str,
    url_name: str,
    icon: str = "fa-regular fa-circle",
    active_url_names=None,
    active_app_names=None,
    active_url_name_contains=None,
):
    active_url_names = active_url_names or []
    active_app_names = active_app_names or []
    active_url_name_contains = active_url_name_contains or []

    url = _safe_reverse(url_name)
    if not url:
        return None

    current_url_name, current_app_name = _current_route_state(request)
    target_url_name = url_name.split(":")[-1]

    match_score = 0
    if current_url_name == target_url_name:
        match_score = 400
    elif current_url_name in active_url_names:
        match_score = 300
    elif any(token and token in current_url_name for token in active_url_name_contains):
        match_score = 200
    elif current_app_name in active_app_names:
        match_score = 100

    return {
        "label": label,
        "url": url,
        "icon": icon,
        "is_active": match_score > 0,
        "_match_score": match_score,
    }


def _normalize_active_items(sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    best_score = 0
    best_item = None

    for section in sections:
        for item in section.get("items", []):
            score = int(item.get("_match_score") or 0)
            if score > best_score:
                best_score = score
                best_item = item

    if best_score <= 0:
        return sections

    for section in sections:
        for item in section.get("items", []):
            item["is_active"] = item is best_item
            item.pop("_match_score", None)

    return sections


def _section(label: str, icon: str, items: List[Optional[Dict[str, Any]]]):
    clean_items = [item for item in items if item]
    if not clean_items:
        return None
    return {
        "label": label,
        "icon": icon,
        "items": clean_items,
    }


def _append_section(sections: List[Dict[str, Any]], section):
    if section and section.get("items"):
        sections.append(section)


def _get_pending_approval_count() -> int:
    try:
        from apps.approvals.selectors import count_pending
        return int(count_pending() or 0)
    except Exception:
        return 0


def _get_meeting_open_count(user) -> int:
    try:
        from django.db.models import Q
        from apps.meeting.models import MeetingSession
        return (
            MeetingSession.objects.filter(
                Q(created_by=user) | Q(participants__user=user),
                status="OPEN",
            )
            .distinct()
            .count()
        )
    except Exception:
        return 0


def _get_care_unread_count(user) -> int:
    try:
        from apps.care.selectors.conversation_selectors import get_unread_count
        return int(get_unread_count(user) or 0)
    except Exception:
        return 0


def _get_helpdesk_open_count(user) -> int:
    """Đếm ticket đang mở liên quan đến user (để hiển thị badge)."""
    try:
        from apps.helpdesk.selectors.ticket_selectors import get_open_ticket_count
        return int(get_open_ticket_count(user) or 0)
    except Exception:
        return 0


def build_sidebar_for_request(request) -> List[Dict[str, Any]]:
    user = request.user
    sections: List[Dict[str, Any]] = []

    is_supperuser = _is_supperuser(user)
    is_manager = _is_manager(user)
    is_sales = _is_sales(user)
    is_doctor = _is_doctor(user)
    is_hr_admin = _is_hr_admin(user)
    is_executive = _is_executive(user)
    can_view_record_completion = _can_view_record_completion(user)
    is_it_admin = _is_it_admin(user)
    is_care = _is_care(user)

    # ── Dashboard tổng quan ──────────────────────────────────────────────────
    items = [
        _item(
            request=request,
            label="Dashboard",
            url_name="dashboard:overview",
            icon="fa-solid fa-house",
            active_app_names=["dashboard"],
            active_url_names=["overview"],
        ),
    ]

    if is_sales or is_executive:
        items += [
            _item(
                request=request,
                label="Danh mục khám",
                url_name="catalogs:category_list",
                icon="fa-solid fa-list-check",
                active_app_names=["catalogs"],
                active_url_name_contains=["category_", "group_"],
            ),
            _item(
                request=request,
                label="Gói khám",
                url_name="catalogs:package_list",
                icon="fa-solid fa-box-open",
                active_app_names=["catalogs"],
                active_url_name_contains=["package_"],
            ),
            _item(
                request=request,
                label="Thư viện",
                url_name="media_library:index",
                icon="fa-regular fa-images",
                active_app_names=["media_library"],
                active_url_name_contains=["index", "media", "library"],
            ),
        ]

    _append_section(sections, _section("Tổng quan", "🏠", items))

    # ── Kinh doanh ──────────────────────────────────────────────────────────
    if is_sales or is_executive:
        _append_section(
            sections,
            _section(
                "Kinh doanh",
                "💼",
                [
                    _item(
                        request=request,
                        label="Tạo báo giá",
                        url_name="contract:create_proposal",
                        icon="fa-solid fa-file-circle-plus",
                        active_url_names=["create_proposal"],
                    ),
                    _item(
                        request=request,
                        label="Danh sách báo giá",
                        url_name="contract:quotation_list",
                        icon="fa-regular fa-file-lines",
                        active_url_names=["quotation_list", "quotation_preview"],
                        active_url_name_contains=["quotation"],
                    ),
                    _item(
                        request=request,
                        label="Tạo hợp đồng",
                        url_name="contract:create_corporate_contract",
                        icon="fa-solid fa-file-signature",
                        active_url_names=["create_corporate_contract"],
                    ),
                    _item(
                        request=request,
                        label="Danh sách hợp đồng",
                        url_name="contract:corporate_contract_list",
                        icon="fa-solid fa-folder-open",
                        active_url_names=[
                            "corporate_contract_list",
                            "corporate_contract_detail",
                            "corporate_contract_preview",
                            "corporate_contract_print",
                        ],
                        active_url_name_contains=["corporate_contract", "contract_preview"],
                    ),
                ],
            ),
        )

    if is_sales or is_executive or is_manager:
        _append_section(
            sections,
            _section(
                "Lịch khám Doanh nghiệp",
                "📅",
                [
                    _item(
                        request=request,
                        label="Đăng ký lịch khám",
                        url_name="contract:create_contract",
                        icon="fa-solid fa-calendar-plus",
                        active_url_names=["create_contract", "edit_contract"],
                    ),
                    _item(
                        request=request,
                        label="Danh sách lịch khám",
                        url_name="contract:contract_list",
                        icon="fa-regular fa-calendar-days",
                        active_url_names=["contract_list", "contract_detail"],
                        active_url_name_contains=["contract_list", "contract_detail"],
                    ),
                    _item(
                        request=request,
                        label="Lịch khám chi tiết",
                        url_name="scheduling:schedule_table",
                        icon="fa-solid fa-table-cells-large",
                        active_app_names=["scheduling"],
                        active_url_name_contains=["schedule"],
                    ),
                    _item(
                        request=request,
                        label="Thống kê lượt khám",
                        url_name="reception:checkin_stats",
                        icon="fa-solid fa-chart-column",
                        active_url_name_contains=["checkin_stats"],
                    ),
                ],
            ),
        )

        _append_section(
            sections,
            _section(
                "Quản lý Doanh nghiệp",
                "🏢",
                [
                    _item(
                        request=request,
                        label="Danh sách triển khai",
                        url_name="contract:implementation_plan_list",
                        icon="fa-solid fa-diagram-project",
                        active_url_names=[
                            "implementation_plan_list",
                            "implementation_plan_detail",
                        ],
                        active_url_name_contains=["implementation_plan"],
                    ),
                    _item(
                        request=request,
                        label="Danh sách KH DN",
                        url_name="organizations:company_list",
                        icon="fa-regular fa-building",
                        active_app_names=["organizations"],
                        active_url_name_contains=["company"],
                    ),
                    _item(
                        request=request,
                        label="Danh sách KH - HIS",
                        url_name="patients:his_patient_sync_list",
                        icon="fa-regular fa-building",
                        active_app_names=["patients"],
                        active_url_name_contains=["his_patient_sync_list"],
                    ),
                    _item(
                        request=request,
                        label="Tiến trình hồ sơ",
                        url_name="record_completion:company_list",
                        icon="fa-solid fa-clipboard-check",
                        active_app_names=["record_completion"],
                        active_url_name_contains=["completion", "pipeline"],
                    ),
                ],
            ),
        )

    # ── KPI ─────────────────────────────────────────────────────────────────
    if can_view_record_completion and not (is_sales or is_executive or is_manager):
        _append_section(
            sections,
            _section(
                "Quản lý Doanh nghiệp",
                "🏢",
                [
                    _item(
                        request=request,
                        label="Tiến trình hồ sơ",
                        url_name="record_completion:company_list",
                        icon="fa-solid fa-clipboard-check",
                        active_app_names=["record_completion"],
                        active_url_name_contains=["completion", "pipeline"],
                    ),
                ],
            ),
        )

    if is_sales or is_executive:
        kpi_items = [
            _item(
                request=request,
                label="Dashboard KPI",
                url_name="targets:dashboard",
                icon="fa-solid fa-bullseye",
                active_app_names=["targets"],
                active_url_name_contains=["dashboard", "target", "quota"],
            )
        ]
        if is_executive:
            kpi_items.append(
                _item(
                    request=request,
                    label="Thiết lập KPI mới",
                    url_name="targets:create",
                    icon="fa-solid fa-sliders",
                    active_url_names=["create"],
                )
            )
        _append_section(sections, _section("KPI & Quota", "🎯", kpi_items))

    # ── Giao việc ────────────────────────────────────────────────────────────
    if _can_use_tasks(user):
        task_items = [
            _item(
                request=request,
                label="Bảng công việc",
                url_name="tasks:board",
                icon="fa-solid fa-table-columns",
                active_app_names=["tasks"],
                active_url_name_contains=["board", "task", "detail"],
            ),
        ]
        if _can_create_task(user):
            task_items.append(
                _item(
                    request=request,
                    label="Giao việc mới",
                    url_name="tasks:create",
                    icon="fa-solid fa-square-plus",
                    active_url_names=["create"],
                )
            )
        _append_section(sections, _section("Giao việc", "📋", task_items))

    # ── Helpdesk – Yêu cầu IT ───────────────────────────────────────────────
    if _can_use_helpdesk(user):
        hd_count = _get_helpdesk_open_count(user)
        hd_list_label = f"Danh sách ticket ({hd_count})" if hd_count else "Danh sách ticket"

        helpdesk_items = [
            _item(
                request=request,
                label=hd_list_label,
                url_name="helpdesk:list",
                icon="fa-solid fa-ticket",
                active_app_names=["helpdesk"],
                active_url_name_contains=["ticket", "helpdesk", "list", "detail"],
            ),
        ]

        if is_executive or is_manager:
            helpdesk_items.append(
                _item(
                    request=request,
                    label="Gửi yêu cầu IT mới",
                    url_name="helpdesk:create",
                    icon="fa-solid fa-paper-plane",
                    active_url_names=["create"],
                )
            )

        _append_section(sections, _section("Yêu cầu IT", "🎫", helpdesk_items))

    # ── Chăm sóc khách hàng ──────────────────────────────────────────────────
    if is_care:
        unread = _get_care_unread_count(user)
        inbox_label = f"Inbox ({unread})" if unread else "Inbox Chat"

        care_items = [
            _item(
                request=request,
                label=inbox_label,
                url_name="care:inbox",
                icon="fa-regular fa-comments",
                active_app_names=["care"],
                active_url_name_contains=["inbox", "conversation", "message"],
            ),
            _item(
                request=request,
                label="Danh sách Telesale",
                url_name="care:contact_list_index",
                icon="fa-solid fa-address-book",
                active_app_names=["care"],
                active_url_name_contains=["contact_list", "contact_detail"],
            ),
        ]

        if is_manager or user.groups.filter(name__in=["Care Admin", "Care Lead"]).exists():
            care_items.append(
                _item(
                    request=request,
                    label="Cài đặt kênh",
                    url_name="care:settings",
                    icon="fa-solid fa-gear",
                    active_url_names=["settings", "channel_create", "channel_edit"],
                )
            )

        _append_section(sections, _section("Chăm sóc KH", "🎧", care_items))

    # ── Lâm sàng ─────────────────────────────────────────────────────────────
    if is_doctor or is_manager:
        _append_section(
            sections,
            _section(
                "Lâm sàng",
                "🩺",
                [
                    _item(
                        request=request,
                        label="Sum Assistant",
                        url_name="clinical:sum_assistant",
                        icon="fa-solid fa-wand-magic-sparkles",
                        active_app_names=["clinical"],
                        active_url_names=["sum_assistant"],
                    ),
                    _item(
                        request=request,
                        label="Khám răng",
                        url_name="clinical:dental_exam_form",
                        icon="fa-solid fa-tooth",
                        active_app_names=["clinical"],
                        active_url_names=["dental_exam_form"],
                    ),
                ],
            ),
        )

    # ── Nhân sự ──────────────────────────────────────────────────────────────
    if is_hr_admin or is_manager:
        hrm_items = [
            _item(
                request=request,
                label="Danh sách nhân viên",
                url_name="hrm:employee_list",
                icon="fa-solid fa-users",
                active_app_names=["hrm"],
                active_url_name_contains=["employee"],
            ),
        ]
        if is_hr_admin or is_manager:
            hrm_items.append(
                _item(
                    request=request,
                    label="Lịch làm việc bác sĩ",
                    url_name="hrm:doctor_schedule_list",
                    icon="fa-solid fa-user-doctor",
                    active_url_name_contains=["doctor_schedule"],
                )
            )
        if is_hr_admin:
            hrm_items.extend(
                [
                    _item(
                        request=request,
                        label="Thêm nhân viên",
                        url_name="hrm:employee_create",
                        icon="fa-solid fa-user-plus",
                        active_url_names=["employee_create"],
                    ),
                    _item(
                        request=request,
                        label="Phòng ban",
                        url_name="hrm:department_list",
                        icon="fa-solid fa-sitemap",
                        active_url_name_contains=["department"],
                    ),
                    _item(
                        request=request,
                        label="Chức vụ",
                        url_name="hrm:position_list",
                        icon="fa-solid fa-id-badge",
                        active_url_name_contains=["position"],
                    ),
                ]
            )
        _append_section(sections, _section("Nhân sự", "👥", hrm_items))

    # ── Phê duyệt ────────────────────────────────────────────────────────────
    approval_items = []
    if is_executive:
        cnt = _get_pending_approval_count()
        approval_items.append(
            _item(
                request=request,
                label=f"Inbox ({cnt})" if cnt else "Inbox phê duyệt",
                url_name="approvals:inbox",
                icon="fa-solid fa-inbox",
                active_url_names=["inbox", "detail"],
                active_app_names=["approvals"],
                active_url_name_contains=["approval"],
            )
        )

    approval_items.append(
        _item(
            request=request,
            label="Yêu cầu của tôi",
            url_name="approvals:my_requests",
            icon="fa-regular fa-clipboard",
            active_url_names=["my_requests"],
            active_app_names=["approvals"],
        )
    )

    _append_section(sections, _section("Phê duyệt", "✅", approval_items))

    # ── Quản lý chất lượng ───────────────────────────────────────────────────
    quality_items = [
        _item(
            request=request,
            label="Báo cáo sự cố",
            url_name="quality:incident_report_list",
            icon="fa-solid fa-triangle-exclamation",
            active_app_names=["quality"],
            active_url_name_contains=["incident"],
        )
    ]
    if is_manager:
        quality_items.append(
            _item(
                request=request,
                label="Kiểm HSBA",
                url_name="quality:medical_record_audit_list",
                icon="fa-solid fa-notes-medical",
                active_app_names=["quality"],
                active_url_name_contains=["audit"],
            )
        )
    _append_section(sections, _section("Quản lý", "📊", quality_items))

    # ── Analytics / Executive ────────────────────────────────────────────────
    if is_executive:
        _append_section(
            sections,
            _section(
                "Thống kê & Báo cáo",
                "📈",
                [
                    _item(
                        request=request,
                        label="Tổng quan doanh thu",
                        url_name="analytics:overview",
                        icon="fa-solid fa-chart-line",
                        active_app_names=["analytics"],
                        active_url_names=["overview"],
                    ),
                    _item(
                        request=request,
                        label="Thống kê dịch vụ",
                        url_name="analytics:service_stats",
                        icon="fa-solid fa-chart-pie",
                        active_app_names=["analytics"],
                        active_url_names=["service_stats"],
                    ),
                ],
            ),
        )

    if is_supperuser:
        _append_section(
            sections,
            _section(
                "Retention & Loyalty",
                "📈",
                [
                    _item(
                        request=request,
                        label="Retention & Loyalty",
                        url_name="retention:overview",
                        icon="fa-solid fa-arrows-rotate",
                        active_app_names=["retention"],
                        active_url_name_contains=["retention"],
                    ),
                ],
            ),
        )

    # ── Quy trình ────────────────────────────────────────────────────────────
    procedure_items = [
        _item(
            request=request,
            label="Danh sách quy trình",
            url_name="procedures:list",
            icon="fa-solid fa-list-ul",
            active_url_name_contains=["list"],
        ),
    ]
    if is_manager or is_hr_admin or is_executive:
        procedure_items.append(
            _item(
                request=request,
                label="Tạo quy trình mới",
                url_name="procedures:create",
                icon="fa-solid fa-diagram-next",
                active_url_names=["create"],
            )
        )
    _append_section(sections, _section("Quy trình", "📋", procedure_items))

    # ── Hệ thống ─────────────────────────────────────────────────────────────
    if is_manager or is_it_admin:
        sys_items = []

        if is_manager:
            sys_items += [
                _item(
                    request=request,
                    label="Thiết lập chung",
                    url_name="scheduling:general_settings",
                    icon="fa-solid fa-sliders",
                    active_url_names=["general_settings"],
                    active_app_names=["scheduling"],
                ),
                _item(
                    request=request,
                    label="Test HIS API",
                    url_name="api_his:api_playground",
                    icon="fa-solid fa-plug",
                    active_url_names=["api_playground"],
                    active_app_names=["api_his"],
                ),
                _item(
                    request=request,
                    label="AI",
                    url_name="ai_assistant:index",
                    icon="fa-solid fa-robot",
                    active_url_names=["index"],
                    active_app_names=["ai_assistant"],
                ),
            ]

        _append_section(sections, _section("Hệ thống", "⚙️", sys_items))

    return _normalize_active_items(sections)
