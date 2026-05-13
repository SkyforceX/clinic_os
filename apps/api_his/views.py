# crm/apps/api_his/views.py
import datetime
from datetime import date
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from apps.booking.models import Appointment
from .pagination import RelativePageNumberPagination
from .serializers import AppointmentBriefSerializer


def _extract_schedule_date(sch) -> date | None:
    """
    Lấy ngày hẹn khám từ AppointmentSchedule với các tên field phổ biến.
    """
    if not sch:
        return None
    for attr in ("start_at", "start_time", "visit_date", "date"):
        if hasattr(sch, attr):
            val = getattr(sch, attr)
            # val có thể là datetime hoặc date
            if val is None:
                continue
            try:
                return val.date() if hasattr(val, "date") else val
            except Exception:
                continue
    return None


class HisAppointmentListView(APIView, RelativePageNumberPagination):
    """
    GET /api/v1/his/appointments/
      ?date=YYYY-MM-DD
      &date_from=YYYY-MM-DD&date_to=YYYY-MM-DD
      &company_id=<id công ty>
      &updated_since=YYYY-MM-DDThh:mm[:ss][Z]
      &page=1&page_size=100
    """
    permission_classes = [IsAuthenticated]
    page_size = 50

    def _parse_dt(self, s):
        if not s:
            return None
        dt = parse_datetime(s)
        if not dt:
            # cho phép đưa ngày → lấy 00:00 local
            d = parse_date(s)
            if d:
                dt = timezone.make_aware(datetime.datetime.combine(d, datetime.time.min))
        if dt and timezone.is_naive(dt):
            dt = timezone.make_aware(dt)
        return dt

    def get(self, request):
        date_str   = request.GET.get("date")
        date_from  = request.GET.get("date_from")
        date_to    = request.GET.get("date_to")
        company_id = request.GET.get("company_id")
        updated_since = request.GET.get("updated_since")

        qs = (
            Appointment.objects
            .select_related(
                "patient",
                "schedule_slot",
                "schedule_slot__contract__company",
            )
            .only(
                "id", "updated_at",
                "patient__ma_bn", "patient__ho_ten", "patient__ngay_sinh",
                "schedule_slot__date",
                "schedule_slot__contract__company__name",
            )
            .filter(schedule_slot__isnull=False)                          # phải có lịch
            .order_by("schedule_slot__date", "id")                        # sắp theo ngày
        )

        # --- Lọc công ty theo hợp đồng của lịch (đúng nguồn dữ liệu) ---
        if company_id:
            qs = qs.filter(schedule_slot__contract__company_id=company_id)

        # --- Lọc updated_since (trên Appointment.updated_at) ---
        if updated_since:
            dt = self._parse_dt(updated_since)
            if dt:
                qs = qs.filter(updated_at__gte=dt)

        if date_from:
            d_from = parse_date(date_from)
            if d_from:
                qs = qs.filter(schedule_slot__date__gte=d_from)
        if date_to:
            d_to = parse_date(date_to)
            if d_to:
                qs = qs.filter(schedule_slot__date__lte=d_to)

        # --- Lọc 1 ngày ---
        if date_str and not (date_from or date_to):
            d = parse_date(date_str)
            if d:
                qs = qs.filter(schedule_slot__date=d)

        # --- Phân trang sau khi đã lọc ---
        page = self.paginate_queryset(qs, request, view=self)

        # --- Build payload (không còn lọc Python) ---
        results = []
        for ap in page:
            bn  = ap.patient
            sch = ap.schedule_slot
            cty = sch.contract.company if sch and sch.contract else None

            results.append({
                "appointment_id": ap.id,
                "ma_bn": getattr(bn, "ma_bn", "") or "",
                "ho_ten": getattr(bn, "ho_ten", "") or "",
                "ngay_sinh": getattr(bn, "ngay_sinh", None),
                "ten_cong_ty": getattr(cty, "name", "") if cty else "",
                "ngay_hen_kham": getattr(sch, "date", None),
            })

        # Serializer để đảm bảo format ngày/thời gian chuẩn
        ser = AppointmentBriefSerializer(results, many=True)
        # không dùng get_paginated_response(ser.data) trực tiếp do có thể bị loại bớt bởi filter Python phía trên
        # => trả page info thủ công dựa theo slice hiện hành.
        # simple: trả như DRF pagination (count/next/previous/results)
        # count thực tế là của queryset trước filter Python.
        # tính count chính xác sau filter Python,
        # => tính total = len(results) + (số record đã bỏ qua ở trang này).
        return Response({
            "count": len(results),     # count thực tế của trang sau filter Python
            "next": self.get_next_link(),
            "previous": self.get_previous_link(),
            "results": ser.data,
        })

# # crm/apps/api_his/views.py
# import datetime
# from datetime import date
# from django.db.models.functions import TruncDate
# from django.utils import timezone
# from django.utils.dateparse import parse_date, parse_datetime
#
# from rest_framework.views import APIView
# from rest_framework.permissions import IsAuthenticated
# from rest_framework.pagination import PageNumberPagination
# from rest_framework.response import Response
#
# from apps.booking.models import Appointment
# from .pagination import RelativePageNumberPagination
# from .serializers import AppointmentBriefSerializer
#
#
# def _extract_schedule_date(sch) -> date | None:
#     """
#     Lấy ngày hẹn khám từ AppointmentSchedule với các tên field phổ biến.
#     Sửa lại phần dưới nếu project bạn dùng field khác.
#     """
#     if not sch:
#         return None
#     for attr in ("start_at", "start_time", "visit_date", "date"):
#         if hasattr(sch, attr):
#             val = getattr(sch, attr)
#             # val có thể là datetime hoặc date
#             if val is None:
#                 continue
#             try:
#                 return val.date() if hasattr(val, "date") else val
#             except Exception:
#                 continue
#     return None
#
#
# class HisAppointmentListView(APIView, RelativePageNumberPagination):
#     """
#     GET /api/v1/his/appointments/
#       ?date=YYYY-MM-DD
#       &date_from=YYYY-MM-DD&date_to=YYYY-MM-DD
#       &company_id=<id công ty>
#       &updated_since=YYYY-MM-DDThh:mm[:ss][Z]
#       &page=1&page_size=100
#     """
#     permission_classes = [IsAuthenticated]
#     page_size = 50
#
#     def _parse_dt(self, s):
#         if not s:
#             return None
#         dt = parse_datetime(s)
#         if not dt:
#             # cho phép đưa ngày → lấy 00:00 local
#             d = parse_date(s)
#             if d:
#                 dt = timezone.make_aware(datetime.datetime.combine(d, datetime.time.min))
#         if dt and timezone.is_naive(dt):
#             dt = timezone.make_aware(dt)
#         return dt
#
#     def get(self, request):
#         date_str   = request.GET.get("date")
#         date_from  = request.GET.get("date_from")
#         date_to    = request.GET.get("date_to")
#         company_id = request.GET.get("company_id")
#         updated_since = request.GET.get("updated_since")
#
#         qs = (
#             Appointment.objects
#             .select_related(
#                 "patient",
#                 "schedule",
#                 "schedule__contract__company",
#             )
#             .only(
#                 "id", "updated_at",
#                 "patient__ma_bn", "patient__ho_ten", "patient__ngay_sinh",
#                 "schedule__date",
#                 "schedule__contract__company__name",
#             )
#             .filter(schedule__isnull=False)                          # phải có lịch
#             .order_by("schedule__date", "id")                        # sắp theo ngày
#         )
#
#         # --- Lọc công ty theo hợp đồng của lịch (đúng nguồn dữ liệu) ---
#         if company_id:
#             qs = qs.filter(schedule__contract__company_id=company_id)
#
#         # --- Lọc updated_since (trên Appointment.updated_at) ---
#         if updated_since:
#             dt = self._parse_dt(updated_since)
#             if dt:
#                 qs = qs.filter(updated_at__gte=dt)
#
#         if date_from:
#             d_from = parse_date(date_from)
#             if d_from:
#                 qs = qs.filter(schedule__date__gte=d_from)
#         if date_to:
#             d_to = parse_date(date_to)
#             if d_to:
#                 qs = qs.filter(schedule__date__lte=d_to)
#
#         # --- Lọc 1 ngày ---
#         if date_str and not (date_from or date_to):
#             d = parse_date(date_str)
#             if d:
#                 qs = qs.filter(schedule__date=d)
#
#         # --- Phân trang sau khi đã lọc ---
#         page = self.paginate_queryset(qs, request, view=self)
#
#         # --- Build payload (không còn lọc Python) ---
#         results = []
#         for ap in page:
#             bn  = ap.patient
#             sch = ap.schedule
#             cty = sch.contract.company if sch and sch.contract else None
#
#             results.append({
#                 "appointment_id": ap.id,
#                 "ma_bn": getattr(bn, "ma_bn", "") or "",
#                 "ho_ten": getattr(bn, "ho_ten", "") or "",
#                 "ngay_sinh": getattr(bn, "ngay_sinh", None),
#                 "ten_cong_ty": getattr(cty, "name", "") if cty else "",
#                 "ngay_hen_kham": getattr(sch, "date", None),
#             })
#
#         # Serializer để đảm bảo format ngày/thời gian chuẩn
#         ser = AppointmentBriefSerializer(results, many=True)
#         # không dùng get_paginated_response(ser.data) trực tiếp do có thể bị loại bớt bởi filter Python phía trên
#         # => trả page info thủ công dựa theo slice hiện hành.
#         # simple: trả như DRF pagination (count/next/previous/results)
#         # count thực tế là của queryset trước filter Python.
#         # tính count chính xác sau filter Python,
#         # => tính total = len(results) + (số record đã bỏ qua ở trang này).
#         return Response({
#             "count": len(results),     # count thực tế của trang sau filter Python
#             "next": self.get_next_link(),
#             "previous": self.get_previous_link(),
#             "results": ser.data,
#         })
