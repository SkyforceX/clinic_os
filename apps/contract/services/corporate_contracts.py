from collections import defaultdict
from datetime import time as dtime
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.forms import ValidationError
from django.shortcuts import get_object_or_404

from apps.contract.models import (
    BloodCollectionSchedule,
    Contract,
    ContractServiceLine,
    CorporateContractProfile,
)
from apps.contract.models.contract import ContractStatus
from apps.contract.services.common import (
    get_next_contract_number,
    parse_date,
    parse_int,
)
from apps.contract.services.corporate_catalog import get_catalog_item_map
from apps.organizations.models import Company


def _safe_int(v, default=0):
    try:
        return int(v or 0)
    except Exception:
        return default


def build_catalog_groups():
    item_map = get_catalog_item_map()
    grouped = defaultdict(list)
    for item in item_map.values():
        grouped[item["group_name"]].append(item)
    return dict(grouped)


def _extract_selected_services(post_data):
    item_map = get_catalog_item_map()
    selected = []
    for code, item in item_map.items():
        if post_data.get(f"service_{code}") != "1":
            continue
        selected.append({
            "code": code,
            "item_name": item["item_name"],
            "description": item.get("description") or "",
            "group_name": item.get("group_name") or "",
            "price_type": "standard",
            "price_male": _safe_int(item.get("price_male")),
            "price_female_single": _safe_int(item.get("price_female_single")),
            "price_female_family": _safe_int(item.get("price_female_family")),
            "checked_male": True,
            "checked_female_single": True,
            "checked_female_family": True,
            "note": "",
        })
    return selected


def _compute_totals(male_count, female_single_count, female_family_count, selected_services):
    subtotal_male = subtotal_female_single = subtotal_female_family = 0
    for item in selected_services:
        if item.get("checked_male", True):
            subtotal_male += male_count * _safe_int(item["price_male"])
        if item.get("checked_female_single", True):
            subtotal_female_single += female_single_count * _safe_int(item["price_female_single"])
        if item.get("checked_female_family", True):
            subtotal_female_family += female_family_count * _safe_int(item["price_female_family"])
    grand_total = subtotal_male + subtotal_female_single + subtotal_female_family
    return {
        "subtotal_male": subtotal_male,
        "subtotal_female_single": subtotal_female_single,
        "subtotal_female_family": subtotal_female_family,
        "grand_total": grand_total,
    }


def _parse_time(s):
    try:
        return dtime.fromisoformat((s or "").strip())
    except (ValueError, TypeError):
        return None


@transaction.atomic
def create_corporate_contract_from_request(request):
    company_id = request.POST.get("company_id")
    if not company_id:
        raise ValidationError("Vui lòng chọn công ty.")

    company = get_object_or_404(Company, pk=company_id)

    for field, attr in [("company_address","address"),("company_phone","phone"),("tax_code","tax_code")]:
        v = (request.POST.get(field) or "").strip()
        if v:
            setattr(company, attr, v)
    company.save(update_fields=["address", "phone", "tax_code"])

    male_count = parse_int(request.POST.get("male_count"), 0)
    female_single_count = parse_int(request.POST.get("female_single_count"), 0)
    female_family_count = parse_int(request.POST.get("female_family_count"), 0)
    employee_count = male_count + female_single_count + female_family_count
    if employee_count <= 0:
        raise ValidationError("Tổng số người khám phải lớn hơn 0.")

    contract_date       = parse_date(request.POST.get("contract_date"), required=False)
    start_date          = parse_date(request.POST.get("start_date"), required=True, field_label="ngày bắt đầu")
    end_date            = parse_date(request.POST.get("end_date"), required=True, field_label="ngày kết thúc")
    reception_from_date = parse_date(request.POST.get("reception_from_date"), required=False)
    deposit_deadline    = parse_date(request.POST.get("deposit_deadline"), required=False)

    blood_time_from = _parse_time(request.POST.get("blood_time_from"))
    blood_time_to   = _parse_time(request.POST.get("blood_time_to"))
    blood_location  = (request.POST.get("blood_collection_location") or "").strip() or None

    try:
        deposit_pct = Decimal(request.POST.get("deposit_pct") or "30")
    except InvalidOperation:
        deposit_pct = Decimal("30")
    settlement_days = parse_int(request.POST.get("settlement_days"), 10)

    # Dịch vụ: ưu tiên QuotationDraft đã lưu
    quotation_obj = None
    quotation_id = request.POST.get("quotation_id") or None
    if quotation_id:
        from apps.contract.models.quotation import QuotationDraft
        try:
            quotation_obj = QuotationDraft.objects.get(pk=quotation_id)
        except QuotationDraft.DoesNotExist:
            pass

    if quotation_obj:
        selected_services = []
        for line in quotation_obj.lines.order_by("display_order"):
            selected_services.append({
                "code": str(line.catalog_id or line.id),
                "item_name": line.item_name,
                "description": line.description or "",
                "group_name": line.group_name or "",
                "subgroup_name": line.subgroup_name or "",
                "price_type": line.price_type or "standard",
                "price_male": int(line.price_male or 0),
                "price_female_single": int(line.price_female_single or 0),
                "price_female_family": int(line.price_female_family or 0),
                "udai_price_male": int(line.udai_price_male or 0),
                "udai_price_fs": int(line.udai_price_fs or 0),
                "udai_price_ff": int(line.udai_price_ff or 0),
                "checked_male": bool(line.checked_male),
                "checked_female_single": bool(line.checked_female_single),
                "checked_female_family": bool(line.checked_female_family),
                "note": line.note or "",
            })
    else:
        selected_services = _extract_selected_services(request.POST)

    if not selected_services:
        raise ValidationError("Vui lòng chọn ít nhất 1 dịch vụ.")

    totals = _compute_totals(male_count, female_single_count, female_family_count, selected_services)
    deposit_amount = int(totals["grand_total"] * deposit_pct / 100)

    contract = Contract.objects.create(
        company=company,
        contract_number=get_next_contract_number(),
        contact_person=(request.POST.get("contact_person") or "").strip(),
        representative_title=(request.POST.get("representative_title") or "").strip(),
        employee_count=employee_count,
        start_date=start_date,
        end_date=end_date,
        reception_from_date=reception_from_date,
        contract_value_text=None,
        deposit_payment_text=None,
        settlement_time_text=None,
        note=(request.POST.get("note") or "").strip() or None,
        created_by=request.user if request.user.is_authenticated else None,
    )

    CorporateContractProfile.objects.create(
        contract=contract,
        quotation=quotation_obj,
        contract_date=contract_date,
        quote_number=(request.POST.get("quote_number") or "").strip() or None,
        quote_date=parse_date(request.POST.get("quote_date"), required=False),
        company_name_snapshot=company.name,
        company_address_snapshot=company.address,
        company_tax_code_snapshot=company.tax_code,
        company_phone_snapshot=company.phone,
        contact_person_snapshot=contract.contact_person,
        representative_title_snapshot=contract.representative_title,
        male_count=male_count,
        female_single_count=female_single_count,
        female_family_count=female_family_count,
        signer_a_name=(request.POST.get("signer_a_name") or "").strip() or None,
        signer_a_title=(request.POST.get("signer_a_title") or "").strip() or None,
        signer_b_name=(request.POST.get("signer_b_name") or "").strip() or None,
        signer_b_title=(request.POST.get("signer_b_title") or "").strip() or None,
        quotation_note=(request.POST.get("quotation_note") or "").strip() or None,
        contract_note=(request.POST.get("contract_note") or "").strip() or None,
        subtotal_male=totals["subtotal_male"],
        subtotal_female_single=totals["subtotal_female_single"],
        subtotal_female_family=totals["subtotal_female_family"],
        grand_total=totals["grand_total"],
        blood_collection_time_from=blood_time_from,
        blood_collection_time_to=blood_time_to,
        blood_collection_location=blood_location,
        deposit_pct=deposit_pct,
        deposit_amount=deposit_amount,
        deposit_deadline=deposit_deadline,
        settlement_days=settlement_days,
    )

    detail_rows = []
    for item in selected_services:
        detail_rows.append(ContractServiceLine(
            contract=contract,
            item_name=item["item_name"],
            description=item["description"],
            group_name=item["group_name"],
            for_male=male_count > 0 and item.get("checked_male", True) and item["price_male"] > 0,
            for_female_single=female_single_count > 0 and item.get("checked_female_single", True) and item["price_female_single"] > 0,
            for_female_family=female_family_count > 0 and item.get("checked_female_family", True) and item["price_female_family"] > 0,
            price_male=str(item["price_male"]),
            price_female_single=str(item["price_female_single"]),
            price_female_family=str(item["price_female_family"]),
        ))
    ContractServiceLine.objects.bulk_create(detail_rows, batch_size=100)

    dates = request.POST.getlist("blood_collection_date[]") or []
    locs = request.POST.getlist("blood_location[]") or []
    people = request.POST.getlist("blood_people_count[]") or []
    staff_counts = request.POST.getlist("blood_staff_count[]") or []
    if not request.user.groups.filter(name="Nurses").exists():
        staff_counts = [0] * len(people)

    blood_rows = []
    for i in range(min(len(dates), len(locs), len(people), len(staff_counts))):
        d_str = (dates[i] or "").strip()
        loc = (locs[i] or "").strip()
        ppl = parse_int(people[i], 0)
        stf = parse_int(staff_counts[i], 0)
        if not d_str and not loc and not ppl:
            continue
        d_obj = parse_date(d_str, required=True, field_label=f"ngày lấy máu dòng {i+1}")
        blood_rows.append(BloodCollectionSchedule(
            contract=contract, collection_date=d_obj,
            location=loc, people_count=ppl, staff_count=stf,
        ))
    if blood_rows:
        BloodCollectionSchedule.objects.bulk_create(blood_rows, batch_size=100)

    contract.distribute_slots()
    return contract


def build_quote_context(contract):
    profile = contract.corporate_profile
    details = contract.service_lines.all().order_by("group_name", "display_order", "id")
    blood_collections = contract.blood_collection_schedules.all().order_by("collection_date", "id")
    return {
        "contract": contract,
        "profile": profile,
        "details": details,
        "blood_collections": blood_collections,
    }