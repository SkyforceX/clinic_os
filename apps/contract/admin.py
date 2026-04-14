
from django.contrib import admin, messages
from django.shortcuts import redirect
from django.utils.safestring import mark_safe

from apps.contract.models.document import DocumentTemplate, IssuedDocument
from apps.contract.models.quotation import QuotationDraft, QuotationLine


@admin.register(DocumentTemplate)
class DocumentTemplateAdmin(admin.ModelAdmin):
    list_display = (
        "id", "code", "name", "doc_type", "version",
        "is_active",
        "current_file",
        "updated_at",
    )
    actions = ["action_upload_new_docx", "action_deactivate", "action_activate"]
    list_filter = ("doc_type", "is_active")
    search_fields = ("code", "name", "version")
    readonly_fields = (
        "created_at", "updated_at",
        "current_file",
    )
    fieldsets = (
        (
            "Thông tin template",
            {
                "fields": (
                    "code", "name", "doc_type", "version", "is_active",
                    "current_file",
                    "docx_file",
                )
            },
        ),
        (
            "Lưu ý dùng DOCX template",
            {
                "fields": (),
                "description": (
                    "<div style='max-width:860px'>"
                    "<p><strong>Khuyến nghị:</strong> upload file <code>.docx</code> thật, không dùng <code>.doc</code>.</p>"
                    "<p><strong>Quotation template</strong>: đặt marker <code>{{ QUOTATION_TABLE }}</code> trên một dòng riêng.</p>"
                    "<p>Quotation keys chuẩn: <code>{{ company_name }}</code>, <code>{{ contact_name }}</code>, "
                    "<code>{{ company_address }}</code>, <code>{{ valid_until }}</code>, <code>{{ pax_from }}</code>, "
                    "<code>{{ male_count }}</code>, <code>{{ female_single_count }}</code>, <code>{{ female_family_count }}</code>, "
                    "<code>{{ note }}</code>, <code>{{ total_male }}</code>, <code>{{ total_female_single }}</code>, "
                    "<code>{{ total_female_family }}</code>, <code>{{ grand_total }}</code>.</p>"
                    "<hr>"
                    "<p><strong>Contract template</strong>: đặt marker <code>{{ CONTRACT_CATALOG_TABLE }}</code> trên một dòng riêng.</p>"
                    "<p>Contract keys chuẩn: <code>{{ contract_number_full }}</code>, <code>{{ issue_date_vi }}</code>, "
                    "<code>{{ signer_a_name }}</code>, <code>{{ signer_a_title }}</code>, "
                    "<code>{{ company_name }}</code>, <code>{{ company_address }}</code>, <code>{{ company_phone }}</code>, "
                    "<code>{{ signer_b_name }}</code>, <code>{{ signer_b_title }}</code>, <code>{{ company_tax_code }}</code>, "
                    "<code>{{ period_text }}</code>, <code>{{ blood_time_text }}</code>, "
                    "<code>{{ blood_collection_location }}</code>, <code>{{ reception_from_date }}</code>, "
                    "<code>{{ deposit_pct }}</code>, <code>{{ deposit_amount }}</code>, "
                    "<code>{{ deposit_deadline }}</code>, <code>{{ settlement_days }}</code>, "
                    "<code>{{ contract_note }}</code>.</p>"
                    "</div>"
                ),
            },
        ),
        ("Thời gian", {"fields": ("created_at", "updated_at")}),
    )

    @admin.display(description="File hiện tại")
    def current_file(self, obj):
        if obj.docx_file:
            filename = obj.docx_file.name.split("/")[-1]
            return format_html(
                '<a href="{}" target="_blank">⬇ {}</a>',
                obj.docx_file.url,
                filename,
            )
        return "—"

    @admin.action(description="✏️ Sửa / Upload file mới")
    def action_upload_new_docx(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(
                request,
                "Chỉ chọn đúng 1 template để sửa.",
                level=messages.WARNING,
            )
            return
        obj = queryset.first()
        return redirect(f"../contract/documenttemplate/{obj.pk}/change/")

    @admin.action(description="🔴 Tắt (is_active = False)")
    def action_deactivate(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"Đã tắt {updated} template.")

    @admin.action(description="🟢 Bật (is_active = True)")
    def action_activate(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"Đã bật {updated} template.")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        if obj.is_active:
            (
                DocumentTemplate.objects.filter(doc_type=obj.doc_type, is_active=True)
                .exclude(pk=obj.pk)
                .update(is_active=False)
            )


@admin.register(IssuedDocument)
class IssuedDocumentAdmin(admin.ModelAdmin):
    list_display = (
        "id", "doc_type", "status", "quotation", "contract",
        "version", "issued_at", "created_by",
    )
    search_fields = (
        "quotation__company_name",
        "contract__company__name",
        "contract__corporate_profile__company_name_snapshot",
    )
    list_filter = ("doc_type", "status")
    readonly_fields = (
        "doc_type",
        "status",
        "quotation",
        "template",
        "version",
        "payload_json",
        "docx_file",
        "pdf_file",
        "issued_at",
        "created_by",
        "created_at",
        "updated_at",
    )


@admin.register(QuotationDraft)
class QuotationDraftAdmin(admin.ModelAdmin):
    list_display = ("id", "company_name", "contact_name", "valid_until", "created_by", "created_at")
    search_fields = ("company_name", "contact_name")


@admin.register(QuotationLine)
class QuotationLineAdmin(admin.ModelAdmin):
    list_display = ("id", "quotation", "item_name", "group_name", "subgroup_name", "display_order")
    search_fields = ("item_name", "quotation__company_name")
