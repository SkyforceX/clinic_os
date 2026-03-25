from background_task import background
from django.utils import timezone
from datetime import timedelta
from .models import HealthContract

@background(schedule=60)
def auto_terminate_contracts():
    today = timezone.now().date()
    expired_date = today - timedelta(days=16)
    qs = HealthContract.objects.filter(
        is_terminated=False,
        created_at__date__lte=expired_date
    )
    updated = 0
    for contract in qs:
        contract.is_terminated = True
        contract.terminated_at = today
        contract.save(update_fields=['is_terminated', 'terminated_at'])
        updated += 1
    print(f"Đã cập nhật {updated} hợp đồng hết hạn.")


# phuc.nh@vietmediclinic.com