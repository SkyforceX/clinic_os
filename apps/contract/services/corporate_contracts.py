from collections import defaultdict

from django.db import transaction
from django.forms import ValidationError
from django.shortcuts import get_object_or_404

from apps.booking.models import (
    BloodCollectionInfo,
    ContractServiceDetail,
    HealthContract,
)
from apps.contract.models import CorporateContractProfile
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
            "price_male": _safe_int(item.get("price_male")),
            "price_female_single": _safe_int(item.get("price_female_single")),
            "price_female_family": _safe_int(item.get("price_female_family")),
        })

    return selected


def _compute_totals(male_count, female_single_count, female_family_count, selected_services):
    subtotal_male = 0
    subtotal_female_single = 0
    subtotal_female_family = 0

    for item in selected_services:
        subtotal_male += male_count * _safe_int(item["price_male"])
        subtotal_female_single += female_single_count * _safe_int(item["price_female_single"])
        subtotal_female_family += female_family_count * _safe_int(item["price_female_family"])

    grand_total = subtotal_male + subtotal_female_single + subtotal_female_family
    return {
        "subtotal_male": subtotal_male,
        "subtotal_female_single": subtotal_female_single,
        "subtotal_female_family": subtotal_female_family,
        "grand_total": grand_total,
    }


@transaction.atomic
def create_corporate_contract_from_request(request):
    company_id = request.POST.get("company_id")
    if not company_id:
        raise ValidationError("Vui lòng chọn công ty.")

    company = get_object_or_404(Company, pk=company_id)

    company_address = (request.POST.get("company_address") or "").strip()
    company_phone = (request.POST.get("company_phone") or "").strip()
    tax_code = (request.POST.get("tax_code") or "").strip()

    if company_address:
        company.address = company_address
    if company_phone:
        company.phone = company_phone
    if tax_code:
        company.tax_code = tax_code
    company.save(update_fields=["address", "phone", "tax_code"])

    male_count = parse_int(request.POST.get("male_count"), 0)
    female_single_count = parse_int(request.POST.get("female_single_count"), 0)
    female_family_count = parse_int(request.POST.get("female_family_count"), 0)

    employee_count = male_count + female_single_count + female_family_count
    if employee_count <= 0:
        raise ValidationError("Tổng số người khám phải lớn hơn 0.")

    start_date = parse_date(request.POST.get("start_date"), required=True, field_label="ngày bắt đầu")
    end_date = parse_date(request.POST.get("end_date"), required=True, field_label="ngày kết thúc")
    reception_from_date = parse_date(request.POST.get("reception_from_date"), required=False)

    selected_services = _extract_selected_services(request.POST)
    if not selected_services:
        raise ValidationError("Vui lòng chọn ít nhất 1 dịch vụ.")

    totals = _compute_totals(
        male_count=male_count,
        female_single_count=female_single_count,
        female_family_count=female_family_count,
        selected_services=selected_services,
    )

    contract = HealthContract.objects.create(
        company=company,
        contract_number=get_next_contract_number(),
        contact_person=(request.POST.get("contact_person") or request.POST.get("representative") or "").strip(),
        representative_title=(request.POST.get("representative_title") or "").strip(),
        employee_count=employee_count,
        start_date=start_date,
        end_date=end_date,
        reception_from_date=reception_from_date,
        contract_value_text=(request.POST.get("contract_value_text") or "").strip() or None,
        deposit_payment_text=(request.POST.get("deposit_payment_text") or "").strip() or None,
        settlement_time_text=(request.POST.get("settlement_time_text") or "").strip() or None,
        note=(request.POST.get("note") or "").strip() or None,
        created_by=request.user if request.user.is_authenticated else None,
    )

    CorporateContractProfile.objects.create(
        contract=contract,
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
    )

    detail_rows = []
    for item in selected_services:
        detail_rows.append(
            ContractServiceDetail(
                contract=contract,
                item_name=item["item_name"],
                description=item["description"],
                group_name=item["group_name"],
                for_male=male_count > 0 and item["price_male"] > 0,
                for_female_single=female_single_count > 0 and item["price_female_single"] > 0,
                for_female_family=female_family_count > 0 and item["price_female_family"] > 0,
                price_male=str(item["price_male"]),
                price_female_single=str(item["price_female_single"]),
                price_female_family=str(item["price_female_family"]),
            )
        )
    ContractServiceDetail.objects.bulk_create(detail_rows, batch_size=100)

    dates = request.POST.getlist("blood_collection_date[]") or []
    locs = request.POST.getlist("blood_location[]") or []
    people = request.POST.getlist("blood_people_count[]") or []
    staff_counts = request.POST.getlist("blood_staff_count[]") or []

    flag_nurse = request.user.groups.filter(name="Nurses").exists()
    if not flag_nurse:
        staff_counts = [0] * len(people)

    row_count = min(len(dates), len(locs), len(people), len(staff_counts))
    blood_rows = []
    for i in range(row_count):
        d_str = (dates[i] or "").strip()
        loc = (locs[i] or "").strip()
        ppl = parse_int(people[i], 0)
        stf = parse_int(staff_counts[i], 0)

        if not d_str and not loc and not ppl and not stf:
            continue

        d_obj = parse_date(d_str, required=True, field_label=f"ngày lấy máu dòng {i+1}")
        blood_rows.append(
            BloodCollectionInfo(
                contract=contract,
                collection_date=d_obj,
                location=loc,
                people_count=ppl,
                staff_count=stf,
            )
        )

    if blood_rows:
        BloodCollectionInfo.objects.bulk_create(blood_rows, batch_size=100)

    contract.distribute_slots()
    return contract


def build_quote_context(contract):
    profile = contract.corporate_profile
    details = contract.service_details.all().order_by("group_name", "id")
    blood_collections = contract.blood_collections.all().order_by("collection_date", "id")

    return {
        "contract": contract,
        "profile": profile,
        "details": details,
        "blood_collections": blood_collections,
    }