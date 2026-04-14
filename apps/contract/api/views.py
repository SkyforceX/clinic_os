from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from apps.contract.selectors.checkup_overview import build_checkup_overview_payload


@login_required(login_url="authentication:staff_login")
@require_POST
def ajax_checkup_overview(request):
    company_id = request.POST.get("company_id")
    if not company_id:
        return JsonResponse({"success": False, "error": "Thiếu company_id"}, status=400)

    payload = build_checkup_overview_payload(user=request.user, company_id=company_id)
    return JsonResponse(payload)


@login_required(login_url="authentication:staff_login")
@require_GET
def api_quotation_packages(request):
    """
    Trả về danh sách gói khám mẫu kèm catalog_id của từng danh mục.
    catalog_id = CheckupCategory.item_code (ứng với id trong catalog.json).
    """
    from apps.catalogs.models import CheckupPackageTemplate

    packages = (
        CheckupPackageTemplate.objects
        .filter(is_active=True)
        .prefetch_related("items__category")
        .order_by("name")
    )

    result = []
    for pkg in packages:
        cat_ids = []
        for item in pkg.items.select_related("category").all():
            code = item.category.item_code
            if code:
                try:
                    cat_ids.append(int(code))
                except (ValueError, TypeError):
                    pass

        result.append({
            "id": pkg.id,
            "name": pkg.name,
            "description": pkg.description or "",
            "category_ids": cat_ids,
            "item_count": len(cat_ids),
        })

    return JsonResponse({"packages": result})
