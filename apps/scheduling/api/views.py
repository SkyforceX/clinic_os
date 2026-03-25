from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from apps.scheduling.selectors.schedule_matrix import build_contract_schedule_matrix


@login_required(login_url="authentication:staff_login")
def schedule_summary_json(request):
    payload = build_contract_schedule_matrix(actor=request.user)
    return JsonResponse(
        {
            "days": [day.strftime("%Y-%m-%d") for day in payload["days"]],
            "daily_am_totals": payload["daily_am_totals"],
            "daily_pm_totals": payload["daily_pm_totals"],
            "rows": [
                {
                    "contract_id": row["contract_id"],
                    "contract_number": row["contract_number"],
                    "company_name": row["company_name"],
                }
                for row in payload["schedule_rows"]
            ],
        }
    )