from apps.scheduling.policies import SchedulingPolicy
from apps.scheduling.selectors.schedule_selectors import get_contract_for_actor
from apps.scheduling.services.allocate_slots import allocate_contract_slots


def redistribute_contract_slots(*, actor, contract_id):
    contract = get_contract_for_actor(user=actor, contract_id=contract_id)
    if not contract:
        raise ValueError("Không tìm thấy hợp đồng.")

    if not SchedulingPolicy.can_redistribute_slots(actor, contract):
        raise PermissionError("Bạn không có quyền phân bổ lại slot cho hợp đồng này.")

    return allocate_contract_slots(contract=contract, actor=actor)