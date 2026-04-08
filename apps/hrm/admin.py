from django import forms
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import path, reverse
from django.utils.safestring import mark_safe

from apps.hrm.models.access_control import AccessLog, PositionGroupMapping
from apps.hrm.models.department import Department, Position
from apps.hrm.models.employee import Employee
from apps.hrm.services import account_service

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# Inline: AccessLog (readonly, 15 gần nhất)
# ─────────────────────────────────────────────────────────────────────────────

class AccessLogInline(admin.TabularInline):
    model   = AccessLog
    extra   = 0
    fields  = ("created_at", "action", "django_group", "actor", "note")
    readonly_fields = ("created_at", "action", "django_group", "actor", "note")
    can_delete = False
    max_num    = 0
    verbose_name_plural = "Lịch sử phân quyền"

    def get_queryset(self, request):
        # Trả về queryset KHÔNG slice.
        #
        # Tại sao không thể giới hạn 15 ở đây:
        #   Django admin gọi get_queryset(request) KHÔNG có obj context,
        #   rồi truyền kết quả vào FormSet(queryset=...) trong _create_formsets.
        #   Bên trong BaseInlineFormSet.__init__ Django tiếp tục gọi:
        #       queryset.filter(employee=obj)
        #   Nếu queryset đã bị slice ([:15]) thì lệnh filter này raise:
        #       TypeError: Cannot filter a query once a slice has been taken.
        #
        #   get_formset cũng không giải quyết được vì Django truyền
        #   queryset=inline.get_queryset(request) riêng khi tạo formset instance,
        #   còn get_formset chỉ trả về FormSet class — bất kỳ kwarg nào
        #   còn sót trong kwargs sẽ bị đẩy vào inlineformset_factory()
        #   và gây lỗi "unexpected keyword argument 'queryset'".
        #
        # Giải pháp: trả về toàn bộ log, Django tự filter theo employee.
        return (
            super().get_queryset(request)
            .select_related("django_group", "actor")
            .order_by("-created_at")
        )


# ─────────────────────────────────────────────────────────────────────────────
# Form: Tạo tài khoản mới
# ─────────────────────────────────────────────────────────────────────────────

class CreateUserForm(forms.Form):
    username = forms.CharField(
        label="Username",
        max_length=150,
        widget=forms.TextInput(attrs={"class": "vTextField", "autocomplete": "off"}),
        help_text="Tên đăng nhập. Chỉ dùng chữ thường, số, dấu chấm.",
    )
    password = forms.CharField(
        label="Mật khẩu",
        max_length=128,
        widget=forms.TextInput(attrs={"class": "vTextField", "autocomplete": "new-password"}),
        help_text="Để trống nếu muốn hệ thống tự sinh mật khẩu ngẫu nhiên.",
        required=False,
    )
    email = forms.EmailField(
        label="Email",
        required=False,
        widget=forms.EmailInput(attrs={"class": "vTextField"}),
        help_text="Để trống thì dùng email cá nhân từ hồ sơ.",
    )
    confirm = forms.BooleanField(
        label="Tôi xác nhận tạo tài khoản cho nhân viên này",
        required=True,
    )

    def clean_username(self):
        u = self.cleaned_data["username"].strip().lower()
        if User.objects.filter(username=u).exists():
            raise forms.ValidationError(f"Username '{u}' đã tồn tại.")
        return u

    def clean_password(self):
        pw = self.cleaned_data.get("password", "").strip()
        if pw and len(pw) < 8:
            raise forms.ValidationError("Mật khẩu phải có ít nhất 8 ký tự.")
        return pw


# ─────────────────────────────────────────────────────────────────────────────
# Form: Liên kết User có sẵn
# ─────────────────────────────────────────────────────────────────────────────

class LinkUserForm(forms.Form):
    user = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True).order_by("username"),
        label="Chọn tài khoản",
        widget=forms.Select(attrs={"class": "vTextField"}),
        help_text="Chỉ hiển thị tài khoản đang hoạt động và chưa liên kết nhân viên nào.",
    )
    overwrite_groups = forms.BooleanField(
        label="Xóa nhóm quyền cũ, cấp lại theo chức vụ",
        required=False,
        initial=True,
    )
    confirm = forms.BooleanField(
        label="Tôi xác nhận liên kết tài khoản này",
        required=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Loại user đã liên kết nhân viên khác
        linked_user_ids = Employee.objects.exclude(
            user__isnull=True
        ).values_list("user_id", flat=True)
        self.fields["user"].queryset = User.objects.filter(
            is_active=True
        ).exclude(id__in=linked_user_ids).order_by("username")


# ─────────────────────────────────────────────────────────────────────────────
# EmployeeAdmin
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = (
        "employee_code", "full_name", "department", "position",
        "status_badge", "employment_type", "hire_date",
        "account_status_col",
    )
    list_filter  = ("status", "employment_type", "department", "position")
    search_fields = (
        "employee_code", "full_name", "phone", "email",
        "id_card_number", "user__username",
    )
    readonly_fields = (
        "uuid", "created_by", "created_at", "updated_at",
        "account_info_panel",
    )
    inlines  = [AccessLogInline]
    ordering = ("full_name",)

    fieldsets = (
        ("Định danh", {
            "fields": ("uuid", "employee_code"),
        }),
        ("Tài khoản hệ thống", {
            "fields": ("account_info_panel",),
            "description": (
                "<div style='color:#666;font-size:13px;margin-bottom:8px'>"
                "Dùng các nút bên dưới để cấp / liên kết / đồng bộ tài khoản. "
                "Không sửa trường <em>user</em> trực tiếp."
                "</div>"
            ),
        }),
        ("Thông tin cá nhân", {
            "fields": (
                "full_name", "gender", "date_of_birth",
                "phone", "email", "address",
            ),
        }),
        ("Giấy tờ pháp lý", {
            "classes": ("collapse",),
            "fields": (
                "id_card_number", "id_card_issued_date", "id_card_issued_by",
                "tax_code", "social_insurance_code",
                "bank_account", "bank_name",
            ),
        }),
        ("Công việc", {
            "fields": (
                "department", "position", "direct_manager",
                "employment_type", "status",
                "hire_date", "probation_end_date", "official_date", "resignation_date",
            ),
        }),
        ("Liên hệ khẩn cấp", {
            "classes": ("collapse",),
            "fields": (
                "emergency_contact_name", "emergency_contact_phone", "emergency_contact_rel",
            ),
        }),
        ("Ghi chú & Audit", {
            "classes": ("collapse",),
            "fields": ("note", "created_by", "created_at", "updated_at"),
        }),
    )

    # ── Custom URLs ───────────────────────────────────────────────────────────

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "<int:employee_id>/create-account/",
                self.admin_site.admin_view(self.view_create_account),
                name="hrm_employee_create_account",
            ),
            path(
                "<int:employee_id>/link-account/",
                self.admin_site.admin_view(self.view_link_account),
                name="hrm_employee_link_account",
            ),
            path(
                "<int:employee_id>/unlink-account/",
                self.admin_site.admin_view(self.view_unlink_account),
                name="hrm_employee_unlink_account",
            ),
            path(
                "<int:employee_id>/sync-groups/",
                self.admin_site.admin_view(self.view_sync_groups),
                name="hrm_employee_sync_groups",
            ),
            path(
                "<int:employee_id>/revoke-groups/",
                self.admin_site.admin_view(self.view_revoke_groups),
                name="hrm_employee_revoke_groups",
            ),
        ]
        return custom + urls

    # ── Readonly panel hiển thị trạng thái tài khoản trong change form ───────

    @admin.display(description="Thông tin tài khoản")
    def account_info_panel(self, obj):
        if not obj.pk:
            return "Lưu hồ sơ trước khi cấp tài khoản."

        create_url  = reverse("admin:hrm_employee_create_account", args=[obj.pk])
        link_url    = reverse("admin:hrm_employee_link_account",   args=[obj.pk])
        sync_url    = reverse("admin:hrm_employee_sync_groups",    args=[obj.pk])
        revoke_url  = reverse("admin:hrm_employee_revoke_groups",  args=[obj.pk])
        unlink_url  = reverse("admin:hrm_employee_unlink_account", args=[obj.pk])

        if obj.user:
            # Đã có tài khoản
            groups_html = "".join(
                f'<span style="background:#1a73e8;color:#fff;padding:2px 8px;'
                f'border-radius:10px;font-size:12px;margin:2px;display:inline-block">'
                f'{g.name}</span>'
                for g in obj.user.groups.all()
            ) or '<em style="color:#999">Chưa có nhóm nào</em>'

            status_color = "#2e7d32" if obj.user.is_active else "#c62828"
            status_text  = "Đang hoạt động" if obj.user.is_active else "Bị khóa"

            return mark_safe(
                """
                <div style="background:#f8f9fa;border:1px solid #dee2e6;
                            border-radius:6px;padding:12px;max-width:600px">
                  <div style="margin-bottom:10px">
                    <strong>Username:</strong>
                    <a href="/admin/auth/user/{uid}/change/" target="_blank"
                       style="font-weight:600">{username}</a>
                    &nbsp;
                    <span style="color:{sc};font-size:12px;font-weight:600">
                      ● {st}
                    </span>
                  </div>
                  <div style="margin-bottom:10px">
                    <strong>Nhóm quyền:</strong><br>
                    <div style="margin-top:4px">{groups}</div>
                  </div>
                  <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px">
                    <a href="{sync_url}" class="button"
                       style="background:#1976d2;color:#fff;padding:4px 12px;
                              border-radius:4px;text-decoration:none;font-size:13px">
                      🔄 Đồng bộ nhóm theo chức vụ
                    </a>
                    <a href="{revoke_url}" class="button"
                       style="background:#f57c00;color:#fff;padding:4px 12px;
                              border-radius:4px;text-decoration:none;font-size:13px"
                       onclick="return confirm('Thu hồi TOÀN BỘ nhóm quyền?')">
                      ⛔ Thu hồi toàn bộ nhóm
                    </a>
                    <a href="{unlink_url}" class="button"
                       style="background:#c62828;color:#fff;padding:4px 12px;
                              border-radius:4px;text-decoration:none;font-size:13px"
                       onclick="return confirm('Hủy liên kết tài khoản? Tài khoản vẫn tồn tại.')">
                      🔓 Hủy liên kết
                    </a>
                  </div>
                </div>
                """,
                uid=obj.user.pk,
                username=obj.user.username,
                sc=status_color,
                st=status_text,
                groups=format_html("{}", groups_html),
                sync_url=sync_url,
                revoke_url=revoke_url,
                unlink_url=unlink_url,
            )
        else:
            # Chưa có tài khoản
            suggested = account_service.suggest_username(obj.full_name)
            return format_html(
                """
                <div style="background:#fff8e1;border:1px solid #ffe082;
                            border-radius:6px;padding:12px;max-width:600px">
                  <p style="margin:0 0 10px;color:#795548">
                    ⚠ Nhân viên chưa có tài khoản hệ thống.
                  </p>
                  <div style="display:flex;gap:8px;flex-wrap:wrap">
                    <a href="{create_url}?suggested={suggested}" class="button"
                       style="background:#2e7d32;color:#fff;padding:4px 12px;
                              border-radius:4px;text-decoration:none;font-size:13px">
                      ➕ Tạo tài khoản mới
                    </a>
                    <a href="{link_url}" class="button"
                       style="background:#1976d2;color:#fff;padding:4px 12px;
                              border-radius:4px;text-decoration:none;font-size:13px">
                      🔗 Liên kết tài khoản có sẵn
                    </a>
                  </div>
                </div>
                """,
                create_url=create_url,
                suggested=suggested,
                link_url=link_url,
            )

    # ── List display helpers ──────────────────────────────────────────────────

    @admin.display(description="Trạng thái", ordering="status")
    def status_badge(self, obj):
        colors = {
            "ACTIVE":     ("#2e7d32", "Đang làm"),
            "PROBATION":  ("#f57c00", "Thử việc"),
            "ON_LEAVE":   ("#0277bd", "Nghỉ phép"),
            "RESIGNED":   ("#757575", "Đã nghỉ"),
            "TERMINATED": ("#c62828", "Chấm dứt"),
        }
        color, label = colors.get(obj.status, ("#757575", obj.get_status_display()))
        return format_html(
            '<span style="color:{c};font-weight:600;font-size:12px">● {l}</span>',
            c=color, l=label,
        )

    @admin.display(description="Tài khoản")
    def account_status_col(self, obj):
        if not obj.user_id:
            return format_html('<span style="color:#999;font-size:12px">— chưa có —</span>')
        color = "#2e7d32" if obj.user.is_active else "#c62828"
        groups = obj.user.groups.values_list("name", flat=True)
        groups_str = ", ".join(groups) if groups else "không có nhóm"
        return format_html(
            '<span style="color:{c};font-weight:600">{u}</span>'
            '<br><span style="color:#666;font-size:11px">{g}</span>',
            c=color,
            u=obj.user.username,
            g=groups_str,
        )

    # ── Admin Actions ─────────────────────────────────────────────────────────

    actions = [
        "action_sync_groups",
        "action_revoke_groups",
        "action_activate_user",
        "action_deactivate_user",
    ]

    @admin.action(description="🔄 Đồng bộ nhóm quyền theo chức vụ (đã có tài khoản)")
    def action_sync_groups(self, request, queryset):
        ok = err = 0
        for emp in queryset.select_related("user", "position"):
            if not emp.user_id:
                self.message_user(
                    request,
                    f"{emp.full_name}: chưa có tài khoản, bỏ qua.",
                    messages.WARNING,
                )
                continue
            try:
                result = account_service.sync_groups_from_position(
                    employee=emp, actor=request.user
                )
                ok += 1
            except Exception as e:
                self.message_user(request, f"{emp.full_name}: {e}", messages.ERROR)
                err += 1
        if ok:
            self.message_user(request, f"Đồng bộ thành công {ok} nhân viên.", messages.SUCCESS)

    @admin.action(description="⛔ Thu hồi toàn bộ nhóm quyền (giữ tài khoản)")
    def action_revoke_groups(self, request, queryset):
        ok = 0
        for emp in queryset.select_related("user"):
            if not emp.user_id:
                continue
            try:
                revoked = account_service.revoke_all_groups(
                    employee=emp, actor=request.user
                )
                ok += 1
            except Exception as e:
                self.message_user(request, f"{emp.full_name}: {e}", messages.ERROR)
        if ok:
            self.message_user(request, f"Thu hồi nhóm thành công {ok} nhân viên.", messages.SUCCESS)

    @admin.action(description="✅ Kích hoạt tài khoản (is_active=True)")
    def action_activate_user(self, request, queryset):
        count = 0
        for emp in queryset.select_related("user"):
            if emp.user_id and not emp.user.is_active:
                emp.user.is_active = True
                emp.user.save(update_fields=["is_active"])
                count += 1
        self.message_user(request, f"Kích hoạt {count} tài khoản.", messages.SUCCESS)

    @admin.action(description="🔒 Khóa tài khoản (is_active=False)")
    def action_deactivate_user(self, request, queryset):
        count = 0
        for emp in queryset.select_related("user"):
            if emp.user_id and emp.user.is_active:
                emp.user.is_active = False
                emp.user.save(update_fields=["is_active"])
                count += 1
        self.message_user(request, f"Đã khóa {count} tài khoản.", messages.SUCCESS)

    # ── Custom Views ──────────────────────────────────────────────────────────

    def _employee_change_url(self, employee_id):
        return reverse("admin:hrm_employee_change", args=[employee_id])

    def view_create_account(self, request, employee_id):
        employee = get_object_or_404(Employee, pk=employee_id)

        if employee.user_id:
            self.message_user(
                request,
                f"{employee.full_name} đã có tài khoản '{employee.user.username}'.",
                messages.WARNING,
            )
            return HttpResponseRedirect(self._employee_change_url(employee_id))

        suggested = request.GET.get("suggested", "") or account_service.suggest_username(employee.full_name)
        auto_pw   = account_service.generate_password()

        if request.method == "POST":
            form = CreateUserForm(request.POST)
            if form.is_valid():
                username = form.cleaned_data["username"]
                password = form.cleaned_data["password"] or auto_pw
                email    = form.cleaned_data["email"]
                try:
                    user = account_service.create_and_link_user(
                        employee=employee,
                        username=username,
                        password=password,
                        actor=request.user,
                        email=email,
                    )
                    groups = list(user.groups.values_list("name", flat=True))
                    self.message_user(
                        request,
                        format_html(
                            "✅ Đã tạo tài khoản <strong>{}</strong> và cấp nhóm: {}. "
                            "<span style='color:#c62828'>Mật khẩu: <code>{}</code> "
                            "— lưu lại ngay, sẽ không hiển thị lại.</span>",
                            username,
                            ", ".join(groups) or "(chưa có mapping)",
                            password if not form.cleaned_data["password"] else "***",
                        ),
                        messages.SUCCESS,
                    )
                    return HttpResponseRedirect(self._employee_change_url(employee_id))
                except Exception as e:
                    self.message_user(request, str(e), messages.ERROR)
        else:
            form = CreateUserForm(initial={"username": suggested})

        # Lấy groups sẽ được cấp (preview)
        from apps.hrm.models.access_control import PositionGroupMapping
        preview_groups = []
        if employee.position:
            preview_groups = list(
                PositionGroupMapping.objects.filter(position=employee.position)
                .values_list("django_group__name", flat=True)
            )

        context = {
            **self.admin_site.each_context(request),
            "title": f"Tạo tài khoản – {employee.full_name}",
            "employee": employee,
            "form": form,
            "auto_password": auto_pw,
            "preview_groups": preview_groups,
            "opts": self.model._meta,
        }
        return render(request, "admin/hrm/employee/create_account.html", context)

    def view_link_account(self, request, employee_id):
        employee = get_object_or_404(Employee, pk=employee_id)

        if employee.user_id:
            self.message_user(
                request,
                f"{employee.full_name} đã có tài khoản '{employee.user.username}'.",
                messages.WARNING,
            )
            return HttpResponseRedirect(self._employee_change_url(employee_id))

        if request.method == "POST":
            form = LinkUserForm(request.POST)
            if form.is_valid():
                user = form.cleaned_data["user"]
                overwrite = form.cleaned_data["overwrite_groups"]
                try:
                    result = account_service.link_existing_user(
                        employee=employee,
                        user=user,
                        actor=request.user,
                        overwrite_groups=overwrite,
                    )
                    self.message_user(
                        request,
                        format_html(
                            "✅ Đã liên kết tài khoản <strong>{}</strong>. "
                            "Nhóm được cấp: {}.",
                            result["username"],
                            ", ".join(result["granted"]) or "(chưa có mapping)",
                        ),
                        messages.SUCCESS,
                    )
                    return HttpResponseRedirect(self._employee_change_url(employee_id))
                except Exception as e:
                    self.message_user(request, str(e), messages.ERROR)
        else:
            form = LinkUserForm()

        # Preview groups
        from apps.hrm.models.access_control import PositionGroupMapping
        preview_groups = []
        if employee.position:
            preview_groups = list(
                PositionGroupMapping.objects.filter(position=employee.position)
                .values_list("django_group__name", flat=True)
            )

        context = {
            **self.admin_site.each_context(request),
            "title": f"Liên kết tài khoản – {employee.full_name}",
            "employee": employee,
            "form": form,
            "preview_groups": preview_groups,
            "opts": self.model._meta,
        }
        return render(request, "admin/hrm/employee/link_account.html", context)

    def view_unlink_account(self, request, employee_id):
        employee = get_object_or_404(Employee, pk=employee_id)
        if not employee.user_id:
            self.message_user(request, "Nhân viên chưa có tài khoản.", messages.WARNING)
            return HttpResponseRedirect(self._employee_change_url(employee_id))

        if request.method == "POST":
            deactivate = request.POST.get("deactivate") == "1"
            try:
                account_service.unlink_user(
                    employee=employee, actor=request.user, deactivate=deactivate
                )
                self.message_user(
                    request,
                    f"Đã hủy liên kết tài khoản. "
                    + ("Tài khoản đã bị khóa." if deactivate else "Tài khoản vẫn hoạt động."),
                    messages.SUCCESS,
                )
            except Exception as e:
                self.message_user(request, str(e), messages.ERROR)
            return HttpResponseRedirect(self._employee_change_url(employee_id))

        context = {
            **self.admin_site.each_context(request),
            "title": f"Hủy liên kết tài khoản – {employee.full_name}",
            "employee": employee,
            "opts": self.model._meta,
        }
        return render(request, "admin/hrm/employee/unlink_account.html", context)

    def view_sync_groups(self, request, employee_id):
        employee = get_object_or_404(Employee, pk=employee_id)
        if not employee.user_id:
            self.message_user(request, "Nhân viên chưa có tài khoản.", messages.WARNING)
            return HttpResponseRedirect(self._employee_change_url(employee_id))

        if request.method == "POST":
            try:
                result = account_service.sync_groups_from_position(
                    employee=employee, actor=request.user
                )
                self.message_user(
                    request,
                    format_html(
                        "🔄 Đồng bộ xong. Thu hồi: <em>{}</em>. Cấp mới: <strong>{}</strong>.",
                        ", ".join(result["revoked"]) or "không có",
                        ", ".join(result["granted"]) or "không có mapping",
                    ),
                    messages.SUCCESS,
                )
            except Exception as e:
                self.message_user(request, str(e), messages.ERROR)
            return HttpResponseRedirect(self._employee_change_url(employee_id))

        # GET → hiển thị confirm
        from apps.hrm.models.access_control import PositionGroupMapping
        current_groups = list(employee.user.groups.values_list("name", flat=True))
        new_groups = []
        if employee.position:
            new_groups = list(
                PositionGroupMapping.objects.filter(position=employee.position)
                .values_list("django_group__name", flat=True)
            )
        context = {
            **self.admin_site.each_context(request),
            "title": f"Đồng bộ nhóm quyền – {employee.full_name}",
            "employee": employee,
            "current_groups": current_groups,
            "new_groups": new_groups,
            "opts": self.model._meta,
        }
        return render(request, "admin/hrm/employee/sync_groups.html", context)

    def view_revoke_groups(self, request, employee_id):
        employee = get_object_or_404(Employee, pk=employee_id)
        if not employee.user_id:
            self.message_user(request, "Nhân viên chưa có tài khoản.", messages.WARNING)
            return HttpResponseRedirect(self._employee_change_url(employee_id))

        if request.method == "POST":
            try:
                revoked = account_service.revoke_all_groups(
                    employee=employee, actor=request.user
                )
                self.message_user(
                    request,
                    f"Đã thu hồi: {', '.join(revoked) or '(không có nhóm nào)'}.",
                    messages.SUCCESS,
                )
            except Exception as e:
                self.message_user(request, str(e), messages.ERROR)
            return HttpResponseRedirect(self._employee_change_url(employee_id))

        current_groups = list(employee.user.groups.values_list("name", flat=True))
        context = {
            **self.admin_site.each_context(request),
            "title": f"Thu hồi nhóm quyền – {employee.full_name}",
            "employee": employee,
            "current_groups": current_groups,
            "opts": self.model._meta,
        }
        return render(request, "admin/hrm/employee/revoke_groups.html", context)


# ─────────────────────────────────────────────────────────────────────────────
# Other admins (unchanged)
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display  = ("name", "code", "parent", "display_order", "is_active")
    list_filter   = ("is_active",)
    search_fields = ("name", "code")
    ordering      = ("display_order", "name")


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display  = ("name", "code", "department", "level", "is_active")
    list_filter   = ("is_active", "department")
    search_fields = ("name", "code")
    ordering      = ("-level", "name")


@admin.register(PositionGroupMapping)
class PositionGroupMappingAdmin(admin.ModelAdmin):
    list_display  = ("position", "django_group", "note")
    list_filter   = ("django_group",)
    search_fields = ("position__name", "django_group__name")
    autocomplete_fields = ["position"]


@admin.register(AccessLog)
class AccessLogAdmin(admin.ModelAdmin):
    list_display  = ("created_at", "employee", "action", "django_group", "actor")
    list_filter   = ("action", "django_group")
    search_fields = ("employee__full_name", "employee__employee_code")
    readonly_fields = ("employee", "action", "django_group", "actor", "note", "created_at")
    ordering      = ("-created_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
