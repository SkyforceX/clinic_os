import json
import logging
from copy import deepcopy

from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import connections
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import TemplateView

from apps.booking.models import Appointment
from apps.booking.services import push_appointment_to_his

_HIS_LOCAL_PG_ALIAS = "his_local_pg"
logger = logging.getLogger(__name__)


def _ensure_local_pg_alias():
    if _HIS_LOCAL_PG_ALIAS in connections.databases:
        return
    pg_cfg = settings.HIS_LOCAL_PG
    default_db = deepcopy(settings.DATABASES.get("default", {}))
    opts = deepcopy(default_db.get("OPTIONS", {}))
    opts["sslmode"] = "disable"
    default_db.update({
        "ENGINE": "django.db.backends.postgresql",
        "NAME": str(pg_cfg.get("NAME", "PK_HCM")),
        "USER": str(pg_cfg.get("USER", "postgres")),
        "PASSWORD": str(pg_cfg.get("PASSWORD", "postgres")),
        "HOST": str(pg_cfg.get("HOST", "127.0.0.1")),
        "PORT": int(pg_cfg.get("PORT", 5432)),
        "OPTIONS": opts,
        "TIME_ZONE": getattr(settings, "TIME_ZONE", None),
    })
    connections.databases[_HIS_LOCAL_PG_ALIAS] = default_db


def _fetch_local_lich_hen_log(limit=10):
    pg_cfg = settings.HIS_LOCAL_PG
    schema = str(pg_cfg.get("SCHEMA", "dbo")).strip() or "dbo"
    _ensure_local_pg_alias()
    with connections[_HIS_LOCAL_PG_ALIAS].cursor() as cursor:
        cursor.execute(
            f"""
            SELECT id, appointment_id, ho_ten, ma_benh_nhan,
                   ngay_bat_dau, noi_dung, pushed_at
            FROM {schema}."ClinicOSLichHenLocal"
            ORDER BY pushed_at DESC
            LIMIT %s
            """,
            [limit],
        )
        columns = [col[0] for col in cursor.description]
        rows = []
        for row in cursor.fetchall():
            d = dict(zip(columns, row))
            for k, v in d.items():
                if hasattr(v, "strftime"):
                    d[k] = v.strftime("%d/%m/%Y %H:%M:%S")
                elif v is None:
                    d[k] = ""
            rows.append(d)
    return rows


def _can_access_api_playground(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or getattr(user, "is_staff", False):
        return True
    return user.groups.filter(
        name__in=["Executive", "Executives", "IT Admin", "IT", "IT Support"]
    ).exists()


@method_decorator(login_required(login_url='authentication:staff_login'), name='dispatch')
class ApiPlaygroundView(TemplateView):
    template_name = "tools/api_playground.html"

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if not request.user.is_authenticated:
            return response
        if not _can_access_api_playground(request.user):
            raise PermissionDenied
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["default_endpoint"] = "/api/v1/his/appointments/"
        return ctx


@method_decorator(login_required(login_url='authentication:staff_login'), name='dispatch')
class BookingHisPushDemoView(TemplateView):
    template_name = "tools/booking_his_push_demo.html"

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if not request.user.is_authenticated:
            return response
        if not _can_access_api_playground(request.user):
            raise PermissionDenied
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["his_local_enabled"] = bool(getattr(settings, "HIS_LOCAL_SYNC_ENABLED", False))
        return ctx


@method_decorator(login_required(login_url='authentication:staff_login'), name='dispatch')
class BookingHisPushSendView(View):
    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if not request.user.is_authenticated:
            return response
        if not _can_access_api_playground(request.user):
            raise PermissionDenied
        return response

    def post(self, request, *args, **kwargs):
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"ok": False, "error": "JSON body không hợp lệ."}, status=400)

        appointment_id = payload.get("appointment_id")
        if not appointment_id:
            return JsonResponse({"ok": False, "error": "Thiếu appointment_id."}, status=400)

        appointment = (
            Appointment.objects.select_related(
                "patient",
                "his_patient_sync",
                "schedule_slot",
                "schedule_slot__contract__company",
                "schedule_slot__quotation__company",
            )
            .filter(pk=appointment_id)
            .first()
        )
        if not appointment:
            return JsonResponse(
                {"ok": False, "error": f"KhÃ´ng tÃ¬m tháº¥y appointment_id={appointment_id}."},
                status=404,
            )

        try:
            result = push_appointment_to_his(appointment, force=bool(payload.get("force")))
        except Exception as exc:
            logger.exception("Failed to push appointment_id=%s to HIS.", appointment_id)
            return JsonResponse({"ok": False, "error": str(exc)}, status=500)

        return JsonResponse(
            {
                "ok": result.success,
                "result": result.to_session_dict(),
            },
            status=200 if result.success or result.skipped_reason else 502,
        )


@method_decorator(login_required(login_url='authentication:staff_login'), name='dispatch')
class BookingHisLocalLogView(View):
    """Trả JSON 10 lịch hẹn mới nhất từ ClinicOSLichHenLocal (chỉ khi local sync enabled)."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"ok": False, "error": "Unauthorized"}, status=401)
        if not _can_access_api_playground(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        if not getattr(settings, "HIS_LOCAL_SYNC_ENABLED", False):
            return JsonResponse({"ok": True, "enabled": False, "rows": []})
        try:
            rows = _fetch_local_lich_hen_log(limit=10)
            return JsonResponse({"ok": True, "enabled": True, "rows": rows})
        except Exception as exc:
            return JsonResponse({"ok": False, "error": str(exc)}, status=500)
