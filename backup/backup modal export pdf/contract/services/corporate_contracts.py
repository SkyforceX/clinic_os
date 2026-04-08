from collections import defaultdict
from datetime import time as dtime
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.forms import ValidationError
from django.utils import timezone

from apps.catalogs.models import CheckupCategory
from apps.contract.models import (
    BloodCollectionSchedule,
    Contract,
    ContractServiceLine,
    CorporateContractProfile,
)
from apps.contract.policies import ContractPolicy
from apps.contract.services.common import (
    money_to_vietnamese_words,
    parse_date,
    parse_datetime_local,
    parse_int,
    parse_money,
    reserve_next_contract_number,
)
from apps.contract.services.document_payloads import build_contract_document_payload
from apps.contract.services.corporate_catalog import get_catalog_item_map
from apps.organizations.selectors.company_selectors import get_company_for_actor
from apps.scheduling.models import ContractScheduleConfig, ScheduleSlot


def _safe_int(v, default=0):
    try:
        return int(v or 0)
    except Exception:
        return default


def _line_decimal_or_none(value):
    if value in (None, "", 0, "0"):
        return None
    return value


def _resolve_catalog_service_from_quotation_line(quotation_line):
    """
    QuotationLine.catalog_id trong code hiện tại chỉ là snapshot/int từ catalog form,
    không đảm bảo là FK thật tới bảng catalogs_checkup_category.
    Vì vậy chỉ gán catalog_service nếu DB thật sự có bản ghi tương ứng.
    """
    catalog_id = getattr(quotation_line, "catalog_id", None)
    if not catalog_id:
        return None
    return CheckupCategory.objects.filter(pk=catalog_id).first()


def _resolve_catalog_service_from_payload_item(item):
    raw_id = item.get("catalog_service_id") or item.get("catalog_id")
    if not raw_id:
        return None
    return CheckupCategory.objects.filter(pk=raw_id).first()


def _build_contract_service_line_from_quotation_line(
    *,
    contract,
    quotation_line,
    order,
    male_count,
    female_single_count,
    female_family_count,
):
    catalog_service = _resolve_catalog_service_from_quotation_line(quotation_line)

    price_male = _safe_int(getattr(quotation_line, "price_male", 0))
    price_female_single = _safe_int(getattr(quotation_line, "price_female_single", 0))
    price_female_family = _safe_int(getattr(quotation_line, "price_female_family", 0))

    checked_male = bool(getattr(quotation_line, "checked_male", False))
    checked_female_single = bool(getattr(quotation_line, "checked_female_single", False))
    checked_female_family = bool(getattr(quotation_line, "checked_female_family", False))

    return ContractServiceLine(
        contract=contract,
        source_quotation_line_id=quotation_line.id,
        catalog_service=catalog_service,
        item_name=quotation_line.item_name,
        description=quotation_line.description or "",
        group_name=quotation_line.group_name or "Khác",
        subgroup_name=getattr(quotation_line, "subgroup_name", "") or "",
        group_name_en=getattr(quotation_line, "group_name_en", "") or "",
        for_male=male_count > 0 and checked_male and price_male > 0,
        for_female_single=female_single_count > 0 and checked_female_single and price_female_single > 0,
        for_female_family=female_family_count > 0 and checked_female_family and price_female_family > 0,
        price_male=_line_decimal_or_none(price_male),
        price_female_single=_line_decimal_or_none(price_female_single),
        price_female_family=_line_decimal_or_none(price_female_family),
        price_type=getattr(quotation_line, "price_type", "standard") or "standard",
        note=getattr(quotation_line, "note", "") or "",
        display_order=order,
    )


def _build_contract_service_line_from_payload_item(
    *,
    contract,
    item,
    order,
    male_count,
    female_single_count,
    female_family_count,
):
    catalog_service = _resolve_catalog_service_from_payload_item(item)

    price_male = _safe_int(item.get("price_male"))
    price_female_single = _safe_int(item.get("price_female_single"))
    price_female_family = _safe_int(item.get("price_female_family"))

    checked_male = bool(item.get("checked_male", item.get("for_male", False)))
    checked_female_single = bool(item.get("checked_female_single", item.get("for_female_single", False)))
    checked_female_family = bool(item.get("checked_female_family", item.get("for_female_family", False)))

    return ContractServiceLine(
        contract=contract,
        source_quotation_line_id=item.get("source_quotation_line_id"),
        catalog_service=catalog_service,
        item_name=item.get("item_name") or "",
        description=item.get("description") or "",
        group_name=item.get("group_name") or "Khác",
        subgroup_name=item.get("subgroup_name") or "",
        group_name_en=item.get("group_name_en") or "",
        for_male=male_count > 0 and checked_male and price_male > 0,
        for_female_single=female_single_count > 0 and checked_female_single and price_female_single > 0,
        for_female_family=female_family_count > 0 and checked_female_family and price_female_family > 0,
        price_male=_line_decimal_or_none(price_male),
        price_female_single=_line_decimal_or_none(price_female_single),
        price_female_family=_line_decimal_or_none(price_female_family),
        price_type=item.get("price_type") or "standard",
        note=item.get("note") or "",
        display_order=order,
    )


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
        selected.append(
            {
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
            }
        )
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


def get_latest_quotation_for_company(company_id):
    if not company_id:
        return None
    from apps.contract.models.quotation import QuotationDraft

    return (
        QuotationDraft.objects
        .filter(company_id=company_id)
        .order_by("-created_at", "-id")
        .first()
    )


def _field_error(field, message):
    return ValidationError({field: [message]})


def _field_error_multi(errors):
    return ValidationError(errors)


def _non_field_error(message):
    return ValidationError({"__all__": [message]})


def get_corporate_contract_for_update(*, contract_id, actor):
    contract = (
        Contract.objects
        .select_for_update()
        .filter(pk=contract_id)
        .first()
    )
    if not contract:
        raise _non_field_error("Không tìm thấy hợp đồng corporate.")

    if not ContractPolicy.can_update(actor, contract):
        if getattr(contract, "is_locked", False):
            raise _non_field_error("Hợp đồng đã chốt, không thể chỉnh sửa.")
        raise _non_field_error("Bạn không có quyền sửa hợp đồng này.")

    return contract


def _parse_contract_form_payload(request, *, quotation_obj):
    male_count = parse_int(request.POST.get("male_count"), 0)
    female_single_count = parse_int(request.POST.get("female_single_count"), 0)
    female_family_count = parse_int(request.POST.get("female_family_count"), 0)

    employee_count = male_count + female_single_count + female_family_count
    if employee_count <= 0:
        raise ValidationError(
            {
                "male_count": ["Cần nhập số lượng người khám hợp lệ."],
                "female_single_count": ["Cần nhập số lượng người khám hợp lệ."],
                "female_family_count": ["Cần nhập số lượng người khám hợp lệ."],
            }
        )

    try:
        start_date = parse_date(request.POST.get("start_date"), required=True, field_label="ngày bắt đầu")
    except ValidationError:
        raise _field_error("start_date", "Vui lòng nhập ngày bắt đầu hợp lệ.")

    try:
        end_date = parse_date(request.POST.get("end_date"), required=True, field_label="ngày kết thúc")
    except ValidationError:
        raise _field_error("end_date", "Vui lòng nhập ngày kết thúc hợp lệ.")

    contract_date = parse_date(request.POST.get("contract_date"), required=False)
    reception_from_date = parse_date(request.POST.get("reception_from_date"), required=False)
    deposit_deadline = parse_date(request.POST.get("deposit_deadline"), required=False)
    
    blood_collection_from_at = None
    blood_collection_to_at = None
    try:
        blood_collection_from_at = parse_datetime_local(
            request.POST.get("blood_collection_from_at"),
            required=False,
            field_label="ngày giờ bắt đầu lấy mẫu",
        )
    except ValidationError:
        raise _field_error("blood_collection_from_at", "Ngày giờ bắt đầu lấy mẫu không hợp lệ.")
    
    try:
        blood_collection_to_at = parse_datetime_local(
            request.POST.get("blood_collection_to_at"),
            required=False,
            field_label="ngày giờ kết thúc lấy mẫu",
        )
    except ValidationError:
        raise _field_error("blood_collection_to_at", "Ngày giờ kết thúc lấy mẫu không hợp lệ.")
    
    if blood_collection_from_at and blood_collection_to_at and blood_collection_to_at < blood_collection_from_at:
        raise _field_error_multi(
            {
                "blood_collection_from_at": ["Khoảng thời gian lấy mẫu không hợp lệ."],
                "blood_collection_to_at": ["Ngày giờ kết thúc phải lớn hơn hoặc bằng ngày giờ bắt đầu."],
            }
        )
    
    blood_location = (request.POST.get("blood_collection_location") or "").strip() or None
    
    try:
        deposit_pct = Decimal(request.POST.get("deposit_pct") or "30")
    except InvalidOperation:
        raise _field_error("deposit_pct", "Tỷ lệ đặt cọc không hợp lệ.")

    settlement_days = parse_int(request.POST.get("settlement_days"), 10)
    if settlement_days <= 0:
        raise _field_error("settlement_days", "Số ngày quyết toán phải lớn hơn 0.")

    selected_services = []
    for line in quotation_obj.lines.order_by("display_order", "id"):
        selected_services.append(
            {
                "source_quotation_line_id": line.id,
                "catalog_id": line.catalog_id,
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
            }
        )

    if not selected_services:
        raise _field_error("quotation_id", "Báo giá chưa có dịch vụ nào để tạo/cập nhật hợp đồng.")

    totals = _compute_totals(male_count, female_single_count, female_family_count, selected_services)
    auto_deposit_amount = int(totals["grand_total"] * deposit_pct / 100)
    deposit_amount = parse_money(request.POST.get("deposit_amount"), default=auto_deposit_amount)
    if deposit_amount < 0:
        raise _field_error("deposit_amount", "Số tiền đặt cọc không hợp lệ.")
    
    deposit_amount_words = (request.POST.get("deposit_amount_words") or "").strip()
    if not deposit_amount_words and deposit_amount > 0:
        deposit_amount_words = money_to_vietnamese_words(deposit_amount)

    blood_dates = request.POST.getlist("blood_collection_date[]")
    blood_locations = request.POST.getlist("blood_location[]")
    blood_people_counts = request.POST.getlist("blood_people_count[]")
    blood_staff_counts = request.POST.getlist("blood_staff_count[]")

    blood_rows = []
    max_len = max(len(blood_dates), len(blood_locations), len(blood_people_counts), len(blood_staff_counts), 0)

    for idx in range(max_len):
        d = parse_date(blood_dates[idx] if idx < len(blood_dates) else None, required=False)
        loc = (blood_locations[idx] if idx < len(blood_locations) else "").strip()
        ppl = parse_int(blood_people_counts[idx] if idx < len(blood_people_counts) else 0, 0)
        stf = parse_int(blood_staff_counts[idx] if idx < len(blood_staff_counts) else 0, 0)

        if not d and not loc and not ppl and not stf:
            continue

        if not d:
            raise ValidationError({"blood_collection_date[]": [f"Dòng lấy máu {idx + 1} chưa nhập ngày."]})

        blood_rows.append(
            {
                "collection_date": d,
                "location": loc,
                "people_count": ppl,
                "staff_count": stf,
            }
        )

    return {
        "male_count": male_count,
        "female_single_count": female_single_count,
        "female_family_count": female_family_count,
        "employee_count": employee_count,
        "contract_date": contract_date,
        "start_date": start_date,
        "end_date": end_date,
        "reception_from_date": reception_from_date,
        "deposit_deadline": deposit_deadline,
        "blood_collection_from_at": blood_collection_from_at,
        "blood_collection_to_at": blood_collection_to_at,
        "blood_location": blood_location,
        "deposit_pct": deposit_pct,
        "settlement_days": settlement_days,
        "selected_services": selected_services,
        "totals": totals,
        "deposit_amount": deposit_amount,
        "deposit_amount_words": deposit_amount_words,
        "blood_rows": blood_rows,
    }


@transaction.atomic
def create_corporate_contract_from_request(request):
    quotation_id = request.POST.get("quotation_id") or None
    if not quotation_id:
        raise ValidationError({"quotation_id": ["Vui lòng chọn báo giá để tạo hợp đồng."]})

    from apps.contract.models.quotation import QuotationDraft

    quotation_obj = (
        QuotationDraft.objects
        .select_for_update()
        .filter(pk=quotation_id)
        .first()
    )
    if not quotation_obj:
        raise ValidationError({"quotation_id": ["Báo giá không tồn tại hoặc đã bị xóa."]})

    if not quotation_obj.company_id:
        raise ValidationError({"quotation_id": ["Báo giá này chưa gắn công ty, không thể tạo hợp đồng."]})

    if quotation_obj.is_locked:
        raise ValidationError({"quotation_id": ["Báo giá này đang bị khóa."]})

    existing_profile = (
        CorporateContractProfile.objects
        .select_related("contract")
        .filter(quotation_id=quotation_obj.id)
        .first()
    )
    if existing_profile:
        raise ValidationError({"quotation_id": ["Báo giá này đã phát sinh hợp đồng, không thể dùng lại."]})

    latest_quotation = get_latest_quotation_for_company(quotation_obj.company_id)
    if not latest_quotation or latest_quotation.id != quotation_obj.id:
        raise ValidationError({"quotation_id": ["Chỉ được tạo hợp đồng từ báo giá mới nhất của công ty này."]})

    company = get_company_for_actor(user=request.user, company_id=quotation_obj.company_id)
    if not company:
        raise ValidationError({"company_id": ["Bạn không có quyền truy cập công ty gắn với báo giá này."]})

    for field, attr in [("company_address", "address"), ("company_phone", "phone"), ("tax_code", "tax_code")]:
        v = (request.POST.get(field) or "").strip()
        if v:
            setattr(company, attr, v)
    company.save(update_fields=["address", "phone", "tax_code"])

    payload = _parse_contract_form_payload(request, quotation_obj=quotation_obj)
    
    contract = Contract.objects.create(
        company=company,
        contract_number=reserve_next_contract_number(),
        contact_person=(request.POST.get("contact_person") or "").strip(),
        representative_title=(request.POST.get("representative_title") or "").strip(),
        employee_count=payload["employee_count"],
        start_date=payload["start_date"],
        end_date=payload["end_date"],
        reception_from_date=payload["reception_from_date"],
        contract_value_text=None,
        deposit_payment_text=None,
        settlement_time_text=None,
        note=(request.POST.get("note") or "").strip() or None,
        created_by=request.user if request.user.is_authenticated else None,
        is_locked=False,
    )

    profile = CorporateContractProfile.objects.create(
        contract=contract,
        quotation=quotation_obj,
        contract_date=payload["contract_date"],
        quote_number=(request.POST.get("quote_number") or "").strip() or None,
        quote_date=parse_date(request.POST.get("quote_date"), required=False),
        company_name_snapshot=company.name,
        company_address_snapshot=company.address,
        company_tax_code_snapshot=company.tax_code,
        company_phone_snapshot=company.phone,
        contact_person_snapshot=contract.contact_person,
        representative_title_snapshot=contract.representative_title,
        male_count=payload["male_count"],
        female_single_count=payload["female_single_count"],
        female_family_count=payload["female_family_count"],
        signer_a_name=(request.POST.get("signer_a_name") or "").strip() or None,
        signer_a_title=(request.POST.get("signer_a_title") or "").strip() or None,
        signer_b_name=(request.POST.get("signer_b_name") or "").strip() or None,
        signer_b_title=(request.POST.get("signer_b_title") or "").strip() or None,
        quotation_note=(request.POST.get("quotation_note") or "").strip() or None,
        contract_note=(request.POST.get("contract_note") or "").strip() or None,
        subtotal_male=payload["totals"]["subtotal_male"],
        subtotal_female_single=payload["totals"]["subtotal_female_single"],
        subtotal_female_family=payload["totals"]["subtotal_female_family"],
        grand_total=payload["totals"]["grand_total"],
        blood_collection_from_at=payload["blood_collection_from_at"],
        blood_collection_to_at=payload["blood_collection_to_at"],
        blood_collection_location=payload["blood_location"],
        deposit_pct=payload["deposit_pct"],
        deposit_amount=payload["deposit_amount"],
        deposit_amount_words=payload["deposit_amount_words"],
        deposit_deadline=payload["deposit_deadline"],
        settlement_days=payload["settlement_days"],
    )

    detail_rows = []
    for order, quotation_line in enumerate(quotation_obj.lines.order_by("display_order", "id"), start=1):
        detail_rows.append(
            _build_contract_service_line_from_quotation_line(
                contract=contract,
                quotation_line=quotation_line,
                order=order,
                male_count=payload["male_count"],
                female_single_count=payload["female_single_count"],
                female_family_count=payload["female_family_count"],
            )
        )

    if detail_rows:
        ContractServiceLine.objects.bulk_create(detail_rows, batch_size=200)

    blood_rows = []
    for row in payload["blood_rows"]:
        blood_rows.append(
            BloodCollectionSchedule(
                contract=contract,
                collection_date=row["collection_date"],
                location=row["location"],
                people_count=row["people_count"],
                staff_count=row["staff_count"],
            )
        )
    
    if blood_rows:
        BloodCollectionSchedule.objects.bulk_create(blood_rows, batch_size=100)
    
    # ================================
    # GẮN LỊCH KHÁM VÀO HỢP ĐỒNG
    # ================================
    schedule_config = ContractScheduleConfig.objects.filter(
        quotation=quotation_obj
    ).first()
    
    if schedule_config:
        schedule_config.contract = profile
        schedule_config.save(update_fields=["contract", "updated_at"])
        
        ScheduleSlot.objects.filter(
            quotation=quotation_obj,
            contract__isnull=True,
        ).update(contract=profile)
    
    return contract


@transaction.atomic
def lock_corporate_contract(*, contract_id, actor):
    contract = (
        Contract.objects
        .select_for_update()
        .filter(pk=contract_id)
        .first()
    )
    if not contract:
        raise ValidationError("Không tìm thấy hợp đồng corporate.")

    can_lock = (
        actor
        and actor.is_authenticated
        and (
            actor.is_superuser
            or ContractPolicy.is_manager(actor)
            or contract.created_by_id == actor.id
        )
    )
    if not can_lock:
        raise ValidationError("Bạn không có quyền chốt hợp đồng này.")

    if contract.is_locked:
        raise ValidationError("Hợp đồng này đã được chốt trước đó.")

    contract.is_locked = True
    contract.locked_at = timezone.now()
    contract.locked_by = actor
    contract.save(update_fields=["is_locked", "locked_at", "locked_by", "updated_at"])

    quotation = getattr(contract.corporate_profile, "quotation", None)
    if quotation and not quotation.is_locked:
        quotation.is_locked = True
        quotation.locked_at = timezone.now()
        quotation.locked_by = actor
        quotation.save(update_fields=["is_locked", "locked_at", "locked_by", "updated_at"])

    return contract


@transaction.atomic
def unlock_corporate_contract(*, contract_id, actor):
    contract = (
        Contract.objects
        .select_for_update()
        .filter(pk=contract_id)
        .first()
    )
    if not contract:
        raise ValidationError("Không tìm thấy hợp đồng corporate.")

    if not actor or not actor.is_authenticated or not actor.is_superuser:
        raise ValidationError("Chỉ superuser mới được gỡ chốt hợp đồng.")

    if not contract.is_locked:
        raise ValidationError("Hợp đồng này hiện chưa bị chốt.")

    contract.is_locked = False
    contract.locked_at = None
    contract.locked_by = None
    contract.save(update_fields=["is_locked", "locked_at", "locked_by", "updated_at"])

    quotation = getattr(contract.corporate_profile, "quotation", None)
    if quotation and quotation.is_locked:
        quotation.is_locked = False
        quotation.locked_at = None
        quotation.locked_by = None
        quotation.save(update_fields=["is_locked", "locked_at", "locked_by", "updated_at"])

    return contract


@transaction.atomic
def update_corporate_contract_from_request(*, contract_id, request):
    contract = get_corporate_contract_for_update(contract_id=contract_id, actor=request.user)
    profile = (
        CorporateContractProfile.objects
        .select_for_update()
        .get(contract=contract)
    )
    quotation_obj = profile.quotation
    if not quotation_obj:
        raise _field_error("quotation_id", "Hợp đồng này không còn báo giá liên kết.")

    if quotation_obj.is_locked and not request.user.is_superuser:
        raise _field_error("quotation_id", "Báo giá liên kết đang bị khóa, không thể cập nhật hợp đồng.")

    payload = _parse_contract_form_payload(request, quotation_obj=quotation_obj)

    company = get_company_for_actor(user=request.user, company_id=contract.company_id)
    if not company:
        raise _field_error("company_id", "Bạn không có quyền truy cập công ty của hợp đồng này.")

    company_address = (request.POST.get("company_address") or "").strip()
    company_phone = (request.POST.get("company_phone") or "").strip()
    tax_code = (request.POST.get("tax_code") or "").strip()

    company.address = company_address
    company.phone = company_phone
    company.tax_code = tax_code
    company.save(update_fields=["address", "phone", "tax_code"])

    contract.contact_person = (request.POST.get("contact_person") or "").strip()
    contract.representative_title = (request.POST.get("representative_title") or "").strip()
    contract.employee_count = payload["employee_count"]
    contract.start_date = payload["start_date"]
    contract.end_date = payload["end_date"]
    contract.reception_from_date = payload["reception_from_date"]
    contract.note = (request.POST.get("note") or "").strip() or None
    contract.save(
        update_fields=[
            "contact_person",
            "representative_title",
            "employee_count",
            "start_date",
            "end_date",
            "reception_from_date",
            "note",
            "updated_at",
        ]
    )

    profile.contract_date = payload["contract_date"]
    profile.company_name_snapshot = company.name
    profile.company_address_snapshot = company.address
    profile.company_tax_code_snapshot = company.tax_code
    profile.company_phone_snapshot = company.phone
    profile.contact_person_snapshot = contract.contact_person
    profile.representative_title_snapshot = contract.representative_title
    profile.male_count = payload["male_count"]
    profile.female_single_count = payload["female_single_count"]
    profile.female_family_count = payload["female_family_count"]
    profile.signer_a_name = (request.POST.get("signer_a_name") or "").strip() or None
    profile.signer_a_title = (request.POST.get("signer_a_title") or "").strip() or None
    profile.signer_b_name = (request.POST.get("signer_b_name") or "").strip() or None
    profile.signer_b_title = (request.POST.get("signer_b_title") or "").strip() or None
    profile.contract_note = (request.POST.get("contract_note") or "").strip() or None
    profile.quotation_note = (request.POST.get("quotation_note") or "").strip() or None
    profile.subtotal_male = payload["totals"]["subtotal_male"]
    profile.subtotal_female_single = payload["totals"]["subtotal_female_single"]
    profile.subtotal_female_family = payload["totals"]["subtotal_female_family"]
    profile.grand_total = payload["totals"]["grand_total"]
    profile.blood_collection_from_at = payload["blood_collection_from_at"]
    profile.blood_collection_to_at = payload["blood_collection_to_at"]
    profile.blood_collection_location = payload["blood_location"]
    profile.deposit_pct = payload["deposit_pct"]
    profile.deposit_amount = payload["deposit_amount"]
    profile.deposit_amount_words = payload["deposit_amount_words"]
    profile.deposit_deadline = payload["deposit_deadline"]
    profile.settlement_days = payload["settlement_days"]
    profile.save()

    contract.service_lines.all().delete()
    detail_rows = []
    for order, item in enumerate(payload["selected_services"], start=1):
        detail_rows.append(
            _build_contract_service_line_from_payload_item(
                contract=contract,
                item=item,
                order=order,
                male_count=payload["male_count"],
                female_single_count=payload["female_single_count"],
                female_family_count=payload["female_family_count"],
            )
        )
    if detail_rows:
        ContractServiceLine.objects.bulk_create(detail_rows, batch_size=200)

    contract.blood_collection_schedules.all().delete()
    blood_rows = []
    for row in payload["blood_rows"]:
        blood_rows.append(
            BloodCollectionSchedule(
                contract=contract,
                collection_date=row["collection_date"],
                location=row["location"],
                people_count=row["people_count"],
                staff_count=row["staff_count"],
            )
        )
    if blood_rows:
        BloodCollectionSchedule.objects.bulk_create(blood_rows, batch_size=100)

    return contract


def build_quote_context(contract):
    profile = contract.corporate_profile

    details = list(contract.service_lines.order_by("display_order", "id"))
    for idx, item in enumerate(details, start=1):
        item.stt = idx

    blood_collections = contract.blood_collection_schedules.order_by("collection_date", "id")
    contract_payload = build_contract_document_payload(contract)

    return {
        "contract": contract,
        "profile": profile,
        "details": details,
        "blood_collections": blood_collections,
        "contract_payload": contract_payload,
    }