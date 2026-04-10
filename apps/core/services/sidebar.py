from __future__ import annotations

from typing import Any, Dict, List, Optional

from django.urls import NoReverseMatch, reverse


def _is_manager(user) -> bool:
    return getattr(user, "is_superuser", False) or user.groups.filter(
        name__in=["Manager", "Managers"]
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

    is_active = (
        current_url_name == target_url_name
        or current_url_name in active_url_names
        or current_app_name in active_app_names
        or any(token and token in current_url_name for token in active_url_name_contains)
    )

    return {
        "label": label,
        "url": url,
        "is_active": is_active,
    }


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


def build_sidebar_for_request(request) -> List[Dict[str, Any]]:
    user = request.user
    sections: List[Dict[str, Any]] = []

    is_manager = _is_manager(user)
    is_sales = _is_sales(user)
    is_doctor = _is_doctor(user)
    is_hr_admin = _is_hr_admin(user)
    is_executive = _is_executive(user)
    is_care = _is_care(user)

    # ── Dashboard tổng quan ──────────────────────────────────────────────────
    user = request.user

    items = [
        # Ai cũng thấy
        _item(
            request=request,
            label="Dashboard",
            url_name="dashboard:overview",
            active_app_names=["dashboard"],
            active_url_names=["overview"],
        ),
    ]

    # Chỉ Sale + Execute (hoặc superadmin)
    if is_sales or is_executive:
        items += [
            _item(
                request=request,
                label="Danh mục khám",
                url_name="catalogs:category_list",
                active_app_names=["catalogs"],
                active_url_name_contains=["category_", "group_"],
            ),
            _item(
                request=request,
                label="Gói khám",
                url_name="catalogs:package_list",
                active_app_names=["catalogs"],
                active_url_name_contains=["package_"],
            ),
            _item(
                request=request,
                label="Thư viện",
                url_name="media_library:index",
                active_app_names=["media_library"],
                active_url_name_contains=["index", "media", "library"],
            ),
        ]

    _append_section(
        sections,
        _section(
            "Tổng quan",
            "🏠",
            items,
        ),
    )

    # ── Kinh doanh / Contract / Catalogs / DN ────────────────────────────────
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
                        active_url_names=["create_proposal"],
                    ),
                    _item(
                        request=request,
                        label="Danh sách báo giá",
                        url_name="contract:quotation_list",
                        active_url_names=["quotation_list", "quotation_preview"],
                        active_url_name_contains=["quotation"],
                    ),
                    _item(
                        request=request,
                        label="Tạo hợp đồng",
                        url_name="contract:create_corporate_contract",
                        active_url_names=["create_corporate_contract"],
                    ),
                    _item(
                        request=request,
                        label="Danh sách hợp đồng",
                        url_name="contract:corporate_contract_list",
                        active_url_names=[
                            "corporate_contract_list",
                            "corporate_contract_detail",
                            "corporate_contract_preview",
                            "corporate_contract_print",
                        ],
                        active_url_name_contains=["corporate_contract", "contract_preview"],
                    )
                ],
            ),
        )

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
                        active_url_names=["create_contract", "edit_contract"],
                    ),
                    _item(
                        request=request,
                        label="Danh sách lịch khám",
                        url_name="contract:contract_list",
                        active_url_names=["contract_list", "contract_detail"],
                        active_url_name_contains=["contract_list", "contract_detail"],
                    ),
                    _item(
                        request=request,
                        label="Lịch khám chi tiết",
                        url_name="scheduling:schedule_table",
                        active_app_names=["scheduling"],
                        active_url_name_contains=["schedule"],
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
                        active_app_names=["organizations"],
                        active_url_name_contains=["company"],
                    ),
                ],
            ),
        )

    # ── KPI ───────────────────────────────────────────────────────────────────
    if is_sales or is_manager or is_executive:
        kpi_items = [
            _item(
                request=request,
                label="Dashboard KPI",
                url_name="targets:dashboard",
                active_app_names=["targets"],
                active_url_name_contains=["dashboard", "target", "quota"],
            )
        ]
        if is_manager or is_executive:
            kpi_items.append(
                _item(
                    request=request,
                    label="Thiết lập KPI mới",
                    url_name="targets:create",
                    active_url_names=["create"],
                )
            )

        _append_section(sections, _section("KPI & Quota", "🎯", kpi_items))

    # ── Giao việc ─────────────────────────────────────────────────────────────
    if _can_use_tasks(user):
        task_items = [
            _item(
                request=request,
                label="Bảng công việc",
                url_name="tasks:board",
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
                    active_url_names=["create"],
                )
            )

        _append_section(sections, _section("Giao việc", "📋", task_items))

    # ── Cuộc họp ──────────────────────────────────────────────────────────────
    # if is_manager or is_executive:
    #     if _is_meeting_participant(user):
    #         upcoming = _get_meeting_open_count(user)
    #         meeting_label = f"Cuộc họp ({upcoming})" if upcoming else "Cuộc họp"

    #         _append_section(
    #             sections,
    #             _section(
    #                 "Cuộc họp",
    #                 "🤝",
    #                 [
    #                     _item(
    #                         request=request,
    #                         label=meeting_label,
    #                         url_name="meeting:session_list",
    #                         active_app_names=["meeting"],
    #                         active_url_name_contains=["session", "meeting"],
    #                     ),
    #                     _item(
    #                         request=request,
    #                         label="Tạo buổi họp",
    #                         url_name="meeting:session_create",
    #                         active_url_names=["session_create"],
    #                     ),
    #                 ],
    #             ),
    #         )

    # ── Chăm sóc khách hàng / chat đa kênh ───────────────────────────────────
    if is_care:
        unread = _get_care_unread_count(user)
        inbox_label = f"Inbox ({unread})" if unread else "Inbox Chat"

        care_items = [
            _item(
                request=request,
                label=inbox_label,
                url_name="care:inbox",
                active_app_names=["care"],
                active_url_name_contains=["inbox", "conversation", "message"],
            ),
            _item(
                request=request,
                label="Danh sách Telesale",
                url_name="care:contact_list_index",
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
                    active_url_names=["settings", "channel_create", "channel_edit"],
                )
            )

        _append_section(sections, _section("Chăm sóc KH", "🎧", care_items))

    # ── Lâm sàng ──────────────────────────────────────────────────────────────
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
                        active_app_names=["clinical"],
                        active_url_names=["sum_assistant"],
                    ),
                    _item(
                        request=request,
                        label="Khám răng",
                        url_name="clinical:dental_exam_form",
                        active_app_names=["clinical"],
                        active_url_names=["dental_exam_form"],
                    ),
                ],
            ),
        )

    # ── Nhân sự ───────────────────────────────────────────────────────────────
    if is_hr_admin or is_manager:
        hrm_items = [
            _item(
                request=request,
                label="Danh sách nhân viên",
                url_name="hrm:employee_list",
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
                        active_url_names=["employee_create"],
                    ),
                    _item(
                        request=request,
                        label="Phòng ban",
                        url_name="hrm:department_list",
                        active_url_name_contains=["department"],
                    ),
                    _item(
                        request=request,
                        label="Chức vụ",
                        url_name="hrm:position_list",
                        active_url_name_contains=["position"],
                    ),
                ]
            )

        _append_section(sections, _section("Nhân sự", "👥", hrm_items))

    # ── Phê duyệt ─────────────────────────────────────────────────────────────
    approval_items = []
    if is_executive:
        cnt = _get_pending_approval_count()
        approval_items.append(
            _item(
                request=request,
                label=f"Inbox ({cnt})" if cnt else "Inbox phê duyệt",
                url_name="approvals:inbox",
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
            active_url_names=["my_requests"],
            active_app_names=["approvals"],
        )
    )

    _append_section(sections, _section("Phê duyệt", "✅", approval_items))

    # ── Quản lý chất lượng ────────────────────────────────────────────────────
    if is_manager:
        _append_section(
            sections,
            _section(
                "Quản lý",
                "📊",
                [
                    _item(
                        request=request,
                        label="Kiểm HSBA",
                        url_name="quality:medical_record_audit_list",
                        active_app_names=["quality"],
                        active_url_name_contains=["audit"],
                    ),
                    _item(
                        request=request,
                        label="Báo cáo sự cố",
                        url_name="quality:incident_report_list",
                        active_app_names=["quality"],
                        active_url_name_contains=["incident"],
                    ),
                ],
            ),
        )

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
                        active_app_names=["analytics"],
                        active_url_names=["overview"],
                    ),
                    _item(
                        request=request,
                        label="Thống kê dịch vụ",
                        url_name="analytics:service_stats",
                        active_app_names=["analytics"],
                        active_url_names=["service_stats"],
                    ),
                    _item(
                        request=request,
                        label="Retention & Loyalty",
                        url_name="retention:overview",
                        active_app_names=["retention"],
                        active_url_name_contains=["retention"],
                    ),
                ],
            ),
        )

    # ── Hệ thống ──────────────────────────────────────────────────────────────
    if is_manager:
        _append_section(
            sections,
            _section(
                "Hệ thống",
                "⚙️",
                [
                    _item(
                        request=request,
                        label="Thiết lập chung",
                        url_name="scheduling:general_settings",
                        active_url_names=["general_settings"],
                        active_app_names=["scheduling"],
                    ),
                    _item(
                        request=request,
                        label="Test HIS API",
                        url_name="api_his:api_playground",
                        active_url_names=["api_playground"],
                        active_app_names=["api_his"],
                    ),
                    _item(
                        request=request,
                        label="AI",
                        url_name="ai_assistant:index",
                        active_url_names=["index"],
                        active_app_names=["ai_assistant"],
                    ),
                ],
            ),
        )

    return sections