from django.urls import include, path

from apps.contract.web.views import (
    ajax_checkup_overview,
    approve_contract,
    checkupcategory_create,
    checkupcategory_edit,
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
    edit_proposal,
    groupcheckup_create,
    issue_quotation_document_view,
    proposal_pdf,
    proposal_preview,
    quotation_list,
    save_contract,
    save_corporate_contract,
    save_quotation,
)

app_name = "contract"

urlpatterns = [
    path("", contract_list, name="contract_list"),
    path("create/", create_contract, name="create_contract"),
    path("save/", save_contract, name="save_contract"),
    path("<int:contract_id>/edit/", edit_contract, name="edit_contract"),
    path("<int:contract_id>/approve/", approve_contract, name="approve_contract"),
    path("<int:contract_id>/delete/", delete_contract, name="delete_contract"),

    path("ajax/checkup-overview/", ajax_checkup_overview, name="ajax_checkup_overview"),

    path("quotations/", quotation_list, name="quotation_list"),
    path("quotations/create/", create_proposal, name="create_proposal"),
    path("quotations/save/", save_quotation, name="save_quotation"),
    path("quotations/<int:quotation_id>/edit/", edit_proposal, name="edit_proposal"),
    path("quotations/<int:quotation_id>/preview/", proposal_preview, name="proposal_preview"),
    path("quotations/<int:quotation_id>/issue/", issue_quotation_document_view, name="issue_quotation_document"),
    path("quotations/issued/<int:issued_id>/docx/", download_issued_quotation_docx, name="download_issued_quotation_docx"),
    path("quotations/issued/<int:issued_id>/pdf/", download_issued_quotation_pdf, name="download_issued_quotation_pdf"),
    path("quotations/<int:pk>/delete/", delete_quotation, name="delete_quotation"),
    path("quotations/export-pdf/", proposal_pdf, name="proposal_pdf"),

    path("catalog/demo-api/", demo_api, name="demo_api"),
    path("catalog/group-checkup/create/", groupcheckup_create, name="groupcheckup_create"),
    path("catalog/checkup-category/create/", checkupcategory_create, name="checkupcategory_create"),
    path("catalog/checkup-category/<int:pk>/edit/", checkupcategory_edit, name="checkupcategory_edit"),

    path("corporate/", corporate_contract_list, name="corporate_contract_list"),
    path("corporate/create/", create_corporate_contract, name="create_corporate_contract"),
    path("corporate/save/", save_corporate_contract, name="save_corporate_contract"),
    path("corporate/<int:contract_id>/quotation/", corporate_quote_print, name="corporate_quote_print"),
    path("corporate/<int:contract_id>/print/", corporate_contract_print, name="corporate_contract_print"),

    path("api/", include("apps.contract.api.urls")),
]