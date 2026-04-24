from django.urls import include, path

from apps.contract.web.views import (
    ajax_checkup_overview,
    approve_contract,
    checkupcategory_create,
    checkupcategory_edit,
    confirm_contract,
    contract_list,
    corporate_contract_list,
    corporate_contract_print,
    corporate_quote_print,
    create_contract,
    create_corporate_contract,
    create_proposal,
    delete_contract,
    delete_quotation,
    demo_api,
    download_issued_quotation_docx,
    download_issued_quotation_pdf,
    edit_contract,
    edit_quotation,
    groupcheckup_create,
    implementation_plan_detail,
    implementation_plan_export_excel,
    implementation_plan_list,
    issue_quotation_document_view,
    quotation_pdf,
    quotation_preview,
    quotation_list,
    save_contract,
    save_corporate_contract,
    save_quotation,
    unlock_corporate_contract_view,
    edit_corporate_contract,
    update_corporate_contract,
)
from apps.contract.web.views.corporate_views import (
    issue_contract_document_view,
    download_issued_contract_docx,
    download_issued_contract_pdf,
    delete_corporate_contract,
)
from apps.contract.web.views.approval_submit_views import (
    submit_quotation_for_approval,
    submit_contract_for_approval,
)

app_name = "contract"

urlpatterns = [
    path("", contract_list, name="contract_list"),
    path("create/", create_contract, name="create_contract"),
    path("save/", save_contract, name="save_contract"),
    path("<int:contract_id>/edit/", edit_contract, name="edit_contract"),
    path("<int:contract_id>/approve/", approve_contract, name="approve_contract"),
    path("<int:contract_id>/confirm/", confirm_contract, name="confirm_contract"),
    path("<int:contract_id>/delete/", delete_contract, name="delete_contract"),

    path("ajax/checkup-overview/", ajax_checkup_overview, name="ajax_checkup_overview"),

    # ── Báo giá ──────────────────────────────────────────────────────────────
    path("quotations/", quotation_list, name="quotation_list"),
    path("quotations/create/", create_proposal, name="create_proposal"),
    path("quotations/save/", save_quotation, name="save_quotation"),
    path("quotations/<int:quotation_id>/edit/", edit_quotation, name="edit_quotation"),
    path("quotations/<int:quotation_id>/preview/", quotation_preview, name="quotation_preview"),
    path("quotations/<int:quotation_id>/issue/", issue_quotation_document_view, name="issue_quotation_document"),
    path("quotations/issued/<int:issued_id>/docx/", download_issued_quotation_docx, name="download_issued_quotation_docx"),
    path("quotations/issued/<int:issued_id>/pdf/", download_issued_quotation_pdf, name="download_issued_quotation_pdf"),
    path("quotations/<int:pk>/delete/", delete_quotation, name="delete_quotation"),
    path("quotations/export-pdf/", quotation_pdf, name="quotation_pdf"),
    # Nộp phê duyệt báo giá
    path("quotations/<int:quotation_id>/submit-approval/", submit_quotation_for_approval, name="submit_quotation_approval"),

    # ── Catalog ───────────────────────────────────────────────────────────────
    path("catalog/demo-api/", demo_api, name="demo_api"),
    path("catalog/group-checkup/create/", groupcheckup_create, name="groupcheckup_create"),
    path("catalog/checkup-category/create/", checkupcategory_create, name="checkupcategory_create"),
    path("catalog/checkup-category/<int:pk>/edit/", checkupcategory_edit, name="checkupcategory_edit"),

    # ── Hợp đồng doanh nghiệp ────────────────────────────────────────────────
    path("corporate/", corporate_contract_list, name="corporate_contract_list"),
    path("corporate/create/", create_corporate_contract, name="create_corporate_contract"),
    path("corporate/save/", save_corporate_contract, name="save_corporate_contract"),
    path("corporate/<int:contract_id>/quotation/", corporate_quote_print, name="corporate_quote_print"),
    path("corporate/<int:contract_id>/print/", corporate_contract_print, name="corporate_contract_print"),
    path("corporate/<int:contract_id>/unlock/", unlock_corporate_contract_view, name="unlock_corporate_contract"),
    path("corporate/<int:contract_id>/edit/", edit_corporate_contract, name="edit_corporate_contract"),
    path("corporate/<int:contract_id>/update/", update_corporate_contract, name="update_corporate_contract"),
    path("corporate/<int:contract_id>/issue/", issue_contract_document_view, name="issue_contract_document"),
    path("corporate/issued/<int:issued_id>/docx/", download_issued_contract_docx, name="download_issued_contract_docx"),
    path("corporate/issued/<int:issued_id>/pdf/", download_issued_contract_pdf, name="download_issued_contract_pdf"),
    path("corporate/<int:pk>/delete/", delete_corporate_contract, name="delete_corporate_contract"),
    # Nộp phê duyệt hợp đồng
    path("corporate/<int:contract_id>/submit-approval/", submit_contract_for_approval, name="submit_contract_approval"),

    # ── Kế hoạch triển khai ───────────────────────────────────────────────────
    path("implementation-plans/", implementation_plan_list, name="implementation_plan_list"),
    path("corporate/<int:contract_id>/implementation/", implementation_plan_detail, name="implementation_plan_detail"),
    path("corporate/<int:contract_id>/implementation/export-excel/", implementation_plan_export_excel, name="implementation_plan_export_excel"),

    path("api/", include("apps.contract.api.urls")),
]
