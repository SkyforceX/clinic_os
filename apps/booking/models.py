from django.db import models
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import User
from apps.organizations.models import Company
from apps.patients.models import Patient
from django.utils import timezone
from django.db.models import Sum
from datetime import timedelta
from django.core.exceptions import ValidationError

from django.conf import settings


class HealthContract(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='contracts')
    contract_number = models.CharField(max_length=50, unique=True, null=True, blank=True)
    contact_person = models.CharField(max_length=255, blank=True)
    representative_title = models.CharField(max_length=255, blank=True)
    employee_count = models.PositiveIntegerField(null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    reception_from_date = models.DateField(null=True, blank=True)
    contract_value_text  = models.TextField(blank=True, null=True)
    deposit_payment_text = models.TextField(blank=True, null=True) 
    settlement_time_text = models.TextField(blank=True, null=True)
    note = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    is_approved = models.BooleanField(default=False) 
    is_terminated = models.BooleanField(default=False)
    is_finished = models.BooleanField(default=False)
    terminated_at = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('company', 'contract_number')

    @property
    def year(self) -> int | None:
        if self.start_date:
            return self.start_date.year
        if self.created_at:
            return self.created_at.year
        return None

    def __str__(self):
        return f"{self.company.name} - HĐ {self.contract_number} ({self.year})"
    
    def distribute_slots(self):
        from apps.scheduling.services.allocate_slots import allocate_contract_slots
        return allocate_contract_slots(contract=self)
    # def distribute_slots(self): # =====> CHIA ĐỀU SLOT CHO CÁC NGÀY TƯƠNG ỨNG SỐ LƯỢNG NHÂN VIÊN
    #     MAX_AM = 100
    #     MAX_PM = 100
    #     total_needed = self.employee_count
    #     days = [
    #         d for d in (
    #             self.start_date + timedelta(days=i)
    #             for i in range((self.end_date - self.start_date).days + 1)
    #         )
    #         if d.weekday() != 6  # 6 = Chủ nhật
    #     ]
    #
    #     # 1. Tính tổng slot còn lại theo từng ngày
    #     available_by_date = {}
    #     total_available = 0
    #
    #     for day in days:
    #         schedules = AppointmentSchedule.objects.filter(date=day).exclude(contract=self)
    #
    #         used_am = sum(s.limit_am for s in schedules if s.shift == 'AM')
    #         used_pm = sum(s.limit_pm for s in schedules if s.shift == 'PM')
    #
    #         remaining_am = max(0, MAX_AM - used_am)
    #         remaining_pm = max(0, MAX_PM - used_pm)
    #         remaining_total = remaining_am + remaining_pm
    #
    #         available_by_date[day] = {'am': remaining_am, 'pm': remaining_pm}
    #         total_available += remaining_total
    #
    #     min_required = len(days) * 2 * 10  # 2 ca/ngày * tối thiểu 10 slot * số ngày
    #     # 2. Kiểm tra đủ slot không
    #     if total_available < min_required:
    #         raise ValidationError(
    #             f"Khoảng thời gian {self.start_date} → {self.end_date} chỉ còn {total_available} slot (sáng + chiều), không đủ cho {total_needed} nhân viên."
    #         )
    #
    #     # 3. Phân bổ đều theo ngày
    #     daily_base = total_needed // len(days)
    #     remainder = total_needed % len(days)
    #     remaining = total_needed
    #
    #     with transaction.atomic():
    #         for day in days:
    #             # if remaining <= 0: # ====> ẩn để áp slot toàn bộ khung thời gian khám của hợp đồng, không giới hạn theo tổng số nhân viên
    #             #     break
    #             expected_today = daily_base + (1 if remainder > 0 else 0)
    #             if remainder > 0:
    #                 remainder -= 1
    #             # chia đều sáng chiều, Sáng nhiều hơn nếu lẻ
    #             am_target = expected_today // 2 + (expected_today % 2)
    #             pm_target = expected_today // 2
    #
    #             am_available = available_by_date[day]['am']
    #             pm_available = available_by_date[day]['pm']
    #
    #             # am_assign = min(am_target, am_available)
    #             # pm_assign = min(pm_target, pm_available)
    #
    #             # Nếu một ca không đủ, dồn sang ca kia
    #             # if am_target > am_assign:
    #             #     extra = min(am_target - am_assign, pm_available - pm_assign)
    #             #     pm_assign += extra
    #
    #             # if pm_target > pm_assign:
    #             #     extra = min(pm_target - pm_assign, am_available - am_assign)
    #             #     am_assign += extra
    #
    #
    #             #==================== slot logic ===============================================#
    #             # Chia đều cho sáng/chiều.
    #             # Nếu đã chia ra ≥10 và slot khả dụng còn đủ: giữ nguyên.
    #             # Nếu chia ra <10 mà slot còn đủ ≥10: set thành 10.
    #             # Nếu slot khả dụng <10: lấy số slot nhỏ nhất có thể.
    #             # Đảm bảo mọi ngày đều có slot đăng ký, và tối thiểu 10 slot nếu còn khả năng.
    #             #===============================================================================#
    #
    #             # am_assign = 10 if am_available >= 10 else am_available
    #             # pm_assign = 10 if pm_available >= 10 else pm_available
    #             # --- AM slot logic ---
    #             if am_target >= 10 and am_available >= am_target:
    #                 am_assign = am_target
    #             elif am_available >= 10:
    #                 am_assign = 10
    #             else:
    #                 am_assign = min(am_target, am_available)
    #
    #             # --- PM slot logic ---
    #             if pm_target >= 10 and pm_available >= pm_target:
    #                 pm_assign = pm_target
    #             elif pm_available >= 10:
    #                 pm_assign = 10
    #             else:
    #                 pm_assign = min(pm_target, pm_available)
    #
    #             # # Nếu một ca không đủ, dồn sang ca kia
    #             # if am_target > am_assign:
    #             #     extra = min(am_target - am_assign, pm_available - pm_assign)
    #             #     pm_assign += extra
    #             # if pm_target > pm_assign:
    #             #     extra = min(pm_target - pm_assign, am_available - am_assign)
    #             #     am_assign += extra
    #
    #             # # Đảm bảo cuối cùng mỗi buổi vẫn tối thiểu 10 slot nếu còn khả năng
    #             # am_assign = min(max(am_assign, 10), am_available) if am_available >= 10 else am_assign
    #             # pm_assign = min(max(pm_assign, 10), pm_available) if pm_available >= 10 else pm_assign
    #
    #             # total_assigned = am_assign + pm_assign
    #
    #             # # Ghi lại vào shift AM
    #             # if am_assign > 0:
    #             #     schedule_am, created = AppointmentSchedule.objects.get_or_create(
    #             #         contract=self,
    #             #         date=day,
    #             #         shift='AM',
    #             #         defaults={
    #             #             'limit_am': am_assign,
    #             #             'limit_pm': 0,
    #             #             'registered_am': 0,
    #             #             'registered_pm': 0,
    #             #         }
    #             #     )
    #             #     if not created:
    #             #         schedule_am.limit_am = am_assign
    #             #         schedule_am.save()
    #
    #             # # Ghi lại vào shift PM
    #             # if pm_assign > 0:
    #             #     schedule_pm, created = AppointmentSchedule.objects.get_or_create(
    #             #         contract=self,
    #             #         date=day,
    #             #         shift='PM',
    #             #         defaults={
    #             #             'limit_am': 0,
    #             #             'limit_pm': pm_assign,
    #             #             'registered_am': 0,
    #             #             'registered_pm': 0,
    #             #         }
    #             #     )
    #             #     if not created:
    #             #         schedule_pm.limit_pm = pm_assign
    #             #         schedule_pm.save()
    #
    #             # remaining -= total_assigned
    #
    #             # --- AM SLOT ---
    #             schedule_am = AppointmentSchedule.objects.filter(contract=self, date=day, shift='AM').first()
    #             if schedule_am:
    #                 reg_am = schedule_am.registered_am
    #                 new_limit_am = max(am_assign, reg_am)
    #                 if schedule_am.limit_am != new_limit_am:
    #                     schedule_am.limit_am = new_limit_am
    #                     schedule_am.save()
    #             else:
    #                 if am_assign > 0:
    #                     AppointmentSchedule.objects.create(
    #                         contract=self,
    #                         date=day,
    #                         shift='AM',
    #                         limit_am=am_assign,
    #                         limit_pm=0,
    #                         registered_am=0,
    #                         registered_pm=0,
    #                     )
    #
    #             # --- PM SLOT ---
    #             schedule_pm = AppointmentSchedule.objects.filter(contract=self, date=day, shift='PM').first()
    #             if schedule_pm:
    #                 reg_pm = schedule_pm.registered_pm
    #                 new_limit_pm = max(pm_assign, reg_pm)
    #                 if schedule_pm.limit_pm != new_limit_pm:
    #                     schedule_pm.limit_pm = new_limit_pm
    #                     schedule_pm.save()
    #             else:
    #                 if pm_assign > 0:
    #                     AppointmentSchedule.objects.create(
    #                         contract=self,
    #                         date=day,
    #                         shift='PM',
    #                         limit_am=0,
    #                         limit_pm=pm_assign,
    #                         registered_am=0,
    #                         registered_pm=0,
    #                     )
    #
    #         # --- XÓA SLOT THỪA (NGÀY NẰM NGOÀI HỢP ĐỒNG, CHƯA AI ĐĂNG KÝ) ---
    #         AppointmentSchedule.objects.filter(
    #             contract=self
    #         ).exclude(date__in=days).annotate(
    #             num_appointments=models.Count('appointments')
    #         ).filter(num_appointments=0).delete()


class ContractServiceDetail(models.Model):
    contract = models.ForeignKey(
        'HealthContract', on_delete=models.CASCADE, related_name='service_details'
    )
    # Lưu liên kết dịch vụ gốc cho tra cứu.
    checkup_category = models.ForeignKey(
        'CheckupCategory', on_delete=models.SET_NULL, null=True, blank=True
    )

    # ==== Snapshot dữ liệu dịch vụ tại thời điểm tạo hợp đồng ====
    item_name = models.CharField(max_length=255)               # Tên dịch vụ lúc tạo hợp đồng
    description = models.TextField(blank=True, null=True)
    group_name = models.CharField(max_length=255, blank=True, null=True)
    group_name_en = models.CharField(max_length=255, blank=True, null=True)

    # ==== Giá và trạng thái từng đối tượng ====
    for_male = models.BooleanField(default=False)
    for_female_single = models.BooleanField(default=False)
    for_female_family = models.BooleanField(default=False)
    # Lưu giá snapshot, có thể là số hoặc text ("TẶNG", "Miễn phí" ...)
    price_male = models.CharField(max_length=50, blank=True, null=True)
    price_female_single = models.CharField(max_length=50, blank=True, null=True)
    price_female_family = models.CharField(max_length=50, blank=True, null=True)

    # ====== Optional ======
    note = models.CharField(max_length=255, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Chi tiết dịch vụ hợp đồng'
        verbose_name_plural = 'Chi tiết dịch vụ hợp đồng'

    def __str__(self):
        return f'{self.contract.contract_number} - {self.item_name}'

    # lấy giá tiền thực tế cho từng đối tượng, trả về số nếu là số, còn lại là chuỗi text như "TẶNG"
    def get_price(self, gender):
        field = f'price_{gender}'
        value = getattr(self, field, None)
        try:
            return int(value.replace(',', '').replace('.', ''))
        except Exception:
            return value or 0


class GroupCheckup(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name


class CheckupCategory(models.Model):
    group_checkup = models.ForeignKey(GroupCheckup, on_delete=models.CASCADE, blank=True, null=True, related_name='categories')
    item_name = models.CharField(max_length=255, verbose_name="Checkup/Test Name")
    description = models.TextField(verbose_name="Description", blank=True, null=True)
    price = models.CharField(max_length=50, verbose_name="Price", blank=True, null=True)

    def __str__(self):
        return f"{self.group_checkup} - {self.item_name}"


class QuotationDraft(models.Model):
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    contact_name = models.CharField(max_length=255)
    company_name = models.CharField(max_length=255)
    company_address = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    valid_until = models.DateField(null=True, blank=True)   # Ngày hết hạn báo giá
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class QuotationDraftDetail(models.Model):
    quotation = models.ForeignKey(QuotationDraft, on_delete=models.CASCADE, related_name='quotation_details')
    item_name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    group_name = models.CharField(max_length=255, blank=True, null=True)
    # Giá gốc (áp dụng chung)
    price = models.DecimalField(max_digits=15, decimal_places=0, blank=True, null=True)

    # Ưu đãi (áp dụng cho từng đối tượng)
    price_male = models.DecimalField(max_digits=15, decimal_places=0, blank=True, null=True)
    price_female_single = models.DecimalField(max_digits=15, decimal_places=0, blank=True, null=True)
    price_female_family = models.DecimalField(max_digits=15, decimal_places=0, blank=True, null=True)

    checked_male = models.BooleanField(default=False, blank=True, null=True)
    checked_female_single = models.BooleanField(default=False, blank=True, null=True)
    checked_female_family = models.BooleanField(default=False, blank=True, null=True)

    # Optionally, loại ưu đãi (miễn phí, %...)
    discount_type_male = models.CharField(max_length=20, blank=True, null=True)  # 'free', 'percent', 'fix'
    discount_value_male = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    discount_type_female_single = models.CharField(max_length=20, blank=True, null=True)  # 'free', 'percent', 'fix'
    discount_value_female_single = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    discount_type_female_family = models.CharField(max_length=20, blank=True, null=True)  # 'free', 'percent', 'fix'
    discount_value_female_family = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)


class BloodCollectionInfo(models.Model):
    contract = models.ForeignKey(HealthContract, on_delete=models.CASCADE, related_name='blood_collections')
    collection_date = models.DateField(verbose_name="Ngày lấy máu")
    location = models.CharField(max_length=100, verbose_name="Địa điểm lấy máu")
    people_count = models.PositiveIntegerField(verbose_name="Số người được lấy máu")
    staff_count = models.PositiveIntegerField(verbose_name="Số lượng nhân viên")


# Buổi khám
class TimeShift(models.TextChoices):
    MORNING = 'AM', _('Sáng')
    AFTERNOON = 'PM', _('Chiều')


class AppointmentSchedule(models.Model):
    contract = models.ForeignKey(HealthContract, on_delete=models.CASCADE, related_name='schedules')
    date = models.DateField(null=True, blank=True,)
    shift = models.CharField(max_length=2, choices=TimeShift.choices)

    # Mỗi lần khách đăng ký sẽ cập nhật 2 field này
    registered_am = models.PositiveIntegerField(default=0)
    registered_pm = models.PositiveIntegerField(default=0)

    # số slot giới hạn phân bổ tự động
    limit_am = models.PositiveIntegerField(default=0)
    limit_pm = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('contract', 'date', 'shift')


# Lịch hẹn cụ thể của từng người gắn với slot
class Appointment(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    schedule = models.ForeignKey(AppointmentSchedule, on_delete=models.CASCADE, null=True, blank=True, related_name='appointments')
    assigned_staff = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('patient', 'schedule')

    def __str__(self):
        return f"{self.patient.ho_ten} - {self.schedule}"

# dành cho khách lẻ chưa định danh
class IndividualBooking(models.Model):
    class Status(models.TextChoices):
        PENDING    = "PENDING", "Chờ xác nhận"
        CONFIRMED  = "CONFIRMED", "Đã xác nhận"
        CHECKED_IN = "CHECKED_IN", "Đã đến quầy"
        CONVERTED  = "CONVERTED", "Đã tạo bệnh nhân/appointment"
        CANCELLED  = "CANCELLED", "Hủy"
        NO_SHOW    = "NO_SHOW", "Vắng"

    # Gắn với slot/buổi ngày
    schedule = models.ForeignKey(
        "booking.AppointmentSchedule",        # 👈 ĐÚNG: ở app booking
        on_delete=models.PROTECT,
        related_name="individual_bookings",
    )

    # Thông tin cá nhân tối thiểu (chưa là Patient)
    full_name = models.CharField(max_length=120)
    gender = models.CharField(max_length=10, blank=True)
    dob = models.DateField(null=True, blank=True)
    phone = models.CharField(max_length=20, db_index=True)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    id_number = models.CharField(max_length=32, blank=True, null=True)  # CMND/CCCD

    reason = models.CharField(max_length=255, blank=True)

    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    note = models.TextField(blank=True)

    # Liên kết chuyển đổi khi đã tạo Patient/Appointment thật
    patient = models.ForeignKey(
        "patients.Patient",                    # 👈 Patient ở app clinic
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="from_bookings",
    )
    appointment = models.OneToOneField(
        "booking.Appointment",              # 👈 Appointment ở app booking
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="from_booking",
    )

    # Audit
    source = models.CharField(max_length=50, blank=True)  # web_form / hotline / qr_offline ...
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["phone", "status"]),
        ]
        constraints = [
            # chống trùng đăng ký "active" cùng ngày/buổi theo phone (+ dob nếu có)
            models.UniqueConstraint(
                fields=["schedule", "phone"],
                condition=models.Q(status__in=["PENDING", "CONFIRMED", "CHECKED_IN"]),
                name="uq_active_booking_by_phone_in_schedule"
            ),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.phone}) @ {self.schedule}"