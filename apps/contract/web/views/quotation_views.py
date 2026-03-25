import re
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.booking.models import CheckupCategory, GroupCheckup, QuotationDraft, QuotationDraftDetail


def _to_decimal(value):
    if value in (None, ""):
        return None
    try:
        cleaned = str(value).replace(",", "").replace(".", "").replace(" ", "")
        return Decimal(cleaned)
    except (InvalidOperation, ValueError, TypeError):
        return None


def _get_price_safe(price):
    try:
        return int(
            str(price)
            .replace(",", "")
            .replace(".", "")
            .replace(" ", "")
            .replace("Miễn phí", "0")
            .replace("TẶNG", "0")
        )
    except Exception:
        return 0


@login_required(login_url="authentication:staff_login")
def quotation_list(request):
    quotations = QuotationDraft.objects.order_by("-created_at")
    return render(request, "contract/staff/quotation_list.html", {"quotations": quotations})


@login_required(login_url="authentication:staff_login")
def create_proposal(request):
    categories = CheckupCategory.objects.select_related("group_checkup").all().order_by("group_checkup__id", "id")
    group_titles = GroupCheckup.objects.all().order_by("name")

    for idx, item in enumerate(categories, start=1):
        item.row_index = idx

    total = 0
    for category in categories:
        total += _get_price_safe(category.price)

    return render(
        request,
        "contract/staff/create_proposal.html",
        {
            "categories": categories,
            "group_titles": group_titles,
            "total": total,
        },
    )


@login_required(login_url="authentication:staff_login")
def proposal_preview(request, quotation_id):
    quotation = get_object_or_404(QuotationDraft, id=quotation_id)
    details = list(quotation.quotation_details.all().order_by("id"))

    for idx, item in enumerate(details, start=1):
        item.row_index = idx

    total_male = sum(_get_price_safe(d.price_male or d.price) for d in details if d.checked_male)
    total_female_single = sum(_get_price_safe(d.price_female_single or d.price) for d in details if d.checked_female_single)
    total_female_family = sum(_get_price_safe(d.price_female_family or d.price) for d in details if d.checked_female_family)

    total = sum(
        _get_price_safe(d.price)
        for d in details
        if (d.checked_male or d.checked_female_single or d.checked_female_family)
    )

    return render(
        request,
        "contract/staff/proposal_preview.html",
        {
            "quotation": quotation,
            "details": details,
            "total": total,
            "total_male": total_male,
            "total_female_single": total_female_single,
            "total_female_family": total_female_family,
        },
    )


@login_required(login_url="authentication:staff_login")
@require_POST
@transaction.atomic
def save_quotation(request):
    contact_name = (request.POST.get("contact_name") or "").strip()
    company_name = (request.POST.get("company_name") or "").strip()
    company_address = (request.POST.get("company_address") or "").strip()

    if not company_name:
        messages.error(request, "Thiếu tên công ty.")
        return redirect("contract:quotation_list")

    service_id_pattern = re.compile(
        r"^service_(\d+)_(male|female_single|female_family|discount|male_price|female_single_price|female_family_price|name|desc|group)$"
    )
    service_ids = set()

    for key in request.POST.keys():
        match = service_id_pattern.match(key)
        if match:
            service_ids.add(match.group(1))

    if not service_ids:
        messages.error(request, "Không có dịch vụ nào được chọn.")
        return redirect("contract:quotation_list")

    quotation = QuotationDraft.objects.create(
        created_by=request.user if request.user.is_authenticated else None,
        contact_name=contact_name,
        company_name=company_name,
        company_address=company_address,
    )

    details = []
    for sid in service_ids:
        checked_male = f"service_{sid}_male" in request.POST
        checked_female_single = f"service_{sid}_female_single" in request.POST
        checked_female_family = f"service_{sid}_female_family" in request.POST

        if not (checked_male or checked_female_single or checked_female_family):
            continue

        item_name = (request.POST.get(f"service_{sid}_name") or "").strip() or None
        description = (request.POST.get(f"service_{sid}_desc") or "").strip() or None
        group_name = (request.POST.get(f"service_{sid}_group") or "").strip() or None

        price_male = _to_decimal(request.POST.get(f"service_{sid}_male_price"))
        price_female_single = _to_decimal(request.POST.get(f"service_{sid}_female_single_price"))
        price_female_family = _to_decimal(request.POST.get(f"service_{sid}_female_family_price"))

        base_price = next(
            (price for price in [price_male, price_female_single, price_female_family] if price is not None),
            None,
        )

        details.append(
            QuotationDraftDetail(
                quotation=quotation,
                item_name=item_name,
                description=description,
                group_name=group_name,
                price=base_price,
                price_male=price_male if checked_male else None,
                price_female_single=price_female_single if checked_female_single else None,
                price_female_family=price_female_family if checked_female_family else None,
                checked_male=checked_male,
                checked_female_single=checked_female_single,
                checked_female_family=checked_female_family,
            )
        )

    if details:
        QuotationDraftDetail.objects.bulk_create(details, batch_size=100)

    messages.success(request, "Đã lưu báo giá thành công.")
    return redirect("contract:proposal_preview", quotation_id=quotation.id)


@login_required(login_url="authentication:staff_login")
def delete_quotation(request, pk):
    quotation = get_object_or_404(QuotationDraft, id=pk)
    if request.method == "POST":
        quotation.delete()
        messages.success(request, "Đã xóa báo giá thành công!")
        return redirect("contract:quotation_list")
    return render(request, "contract/staff/quotation_confirm_delete.html", {"quotation": quotation})


@login_required(login_url="authentication:staff_login")
def proposal_pdf(request):
    messages.info(request, "Chức năng export PDF sẽ refactor riêng ở bước sau.")
    return redirect("contract:quotation_list")