from datetime import date, datetime

from django.forms import ValidationError

from apps.booking.models import HealthContract


def parse_date(value, required=True, field_label="ngày"):
    if not value:
        if required:
            raise ValidationError(f"Vui lòng nhập {field_label}.")
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    value = str(value).strip()
    if not value:
        if required:
            raise ValidationError(f"Vui lòng nhập {field_label}.")
        return None

    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue

    raise ValidationError(
        f"{field_label.capitalize()} không đúng định dạng. Định dạng hợp lệ: dd/mm/yyyy hoặc yyyy-mm-dd."
    )


def parse_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def get_next_contract_number():
    year = datetime.now().year
    contracts = HealthContract.objects.filter(contract_number__endswith=f"/VMD-KD/{year}")
    numbers = set()

    for contract in contracts:
        try:
            num = int(str(contract.contract_number).split("/")[0])
            numbers.add(num)
        except Exception:
            continue

    i = 1
    while i in numbers:
        i += 1

    return f"{i}/VMD-KD/{year}"