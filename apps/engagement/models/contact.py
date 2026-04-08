"""
engagement/models/contact.py
========================
Quản lý danh sách liên hệ telesale với masking số điện thoại.
"""
import uuid

from django.conf import settings
from django.db import models


# ── Contact List (upload từ Excel) ────────────────────────────────────────────

class ContactList(models.Model):
    """Một batch upload danh sách liên hệ."""

    class Status(models.TextChoices):
        DRAFT      = "DRAFT",      "Nháp"
        ACTIVE     = "ACTIVE",     "Đang chạy"
        PAUSED     = "PAUSED",     "Tạm dừng"
        COMPLETED  = "COMPLETED",  "Hoàn thành"
        ARCHIVED   = "ARCHIVED",   "Lưu trữ"

    name        = models.CharField(max_length=255, verbose_name="Tên danh sách")
    description = models.TextField(blank=True, verbose_name="Mô tả")
    status      = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT, db_index=True)
    source_file = models.FileField(upload_to="engagement/uploads/", blank=True, null=True)
    campaign_tag = models.CharField(max_length=100, blank=True, verbose_name="Nhãn chiến dịch")

    # Phân quyền xem số điện thoại đầy đủ
    allow_full_phone_groups = models.JSONField(
        default=list,
        verbose_name="Nhóm được xem SĐT đầy đủ",
        help_text='VD: ["Manager","Engagement Lead"]',
    )

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="engagement_lists_assigned",
        verbose_name="Team lead phụ trách",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="engagement_lists_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table   = "care_contact_list"
        ordering   = ["-created_at"]
        verbose_name = "Danh sách liên hệ"

    def __str__(self):
        return self.name

    @property
    def total_contacts(self):
        return self.contacts.count()

    @property
    def contacted_count(self):
        return self.contacts.filter(status__in=["REACHED", "INTERESTED", "CONVERTED", "NOT_INTERESTED"]).count()

    @property
    def contact_rate(self):
        total = self.total_contacts
        return round(self.contacted_count / total * 100, 1) if total else 0


# ── Contact ───────────────────────────────────────────────────────────────────

class Contact(models.Model):
    """Một liên hệ trong danh sách telesale."""

    class Status(models.TextChoices):
        NEW            = "NEW",            "Mới"
        ASSIGNED       = "ASSIGNED",       "Đã phân công"
        CALLING        = "CALLING",        "Đang liên hệ"
        REACHED        = "REACHED",        "Đã liên hệ được"
        NOT_REACHED    = "NOT_REACHED",    "Không liên hệ được"
        INTERESTED     = "INTERESTED",     "Quan tâm"
        NOT_INTERESTED = "NOT_INTERESTED", "Không quan tâm"
        FOLLOW_UP      = "FOLLOW_UP",      "Cần theo dõi thêm"
        CONVERTED      = "CONVERTED",      "Đã chốt"
        DO_NOT_CALL    = "DO_NOT_CALL",    "Không gọi lại"

    uuid          = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    contact_list  = models.ForeignKey(ContactList, on_delete=models.CASCADE, related_name="contacts")
    status        = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW, db_index=True)

    # ── Thông tin cá nhân ── lưu thô, hiển thị có mask
    full_name     = models.CharField(max_length=255, verbose_name="Họ tên")
    # Số điện thoại lưu nguyên, nhưng chỉ hiển thị mask cho agent
    phone_raw     = models.CharField(max_length=20, db_index=True, verbose_name="SĐT (raw)")
    email         = models.EmailField(blank=True)
    company_name  = models.CharField(max_length=255, blank=True, verbose_name="Tên công ty")
    position      = models.CharField(max_length=100, blank=True, verbose_name="Chức vụ")
    address       = models.TextField(blank=True)

    # ── Metadata từ Excel ──
    extra_data = models.JSONField(default=dict, blank=True, verbose_name="Dữ liệu bổ sung từ file")
    row_number = models.PositiveIntegerField(default=0, verbose_name="Số hàng trong file")

    # ── Assignment & tracking ──
    assigned_to  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="engagement_contacts_assigned",
        verbose_name="Agent phụ trách",
    )
    last_call_at = models.DateTimeField(null=True, blank=True)
    follow_up_at = models.DateTimeField(null=True, blank=True, verbose_name="Hẹn follow-up")
    call_count   = models.PositiveIntegerField(default=0)
    note         = models.TextField(blank=True, verbose_name="Ghi chú tổng")

    # ── Liên kết CRM (nếu đã chốt HĐ)
    linked_company = models.ForeignKey(
        "organizations.Company", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="engagement_contacts",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table   = "care_contact"
        ordering   = ["row_number"]
        verbose_name = "Liên hệ"

    def __str__(self):
        return f"{self.full_name} ({self.phone_masked})"

    @property
    def phone_masked(self) -> str:
        """Hiển thị dạng 090****789 — luôn an toàn để render."""
        p = self.phone_raw or ""
        if len(p) <= 6:
            return "*" * len(p)
        return p[:3] + "****" + p[-3:]

    def phone_for_user(self, user) -> str:
        """Trả về SĐT đầy đủ nếu user có quyền, ngược lại mask."""
        from apps.engagement.policies import EngagementPolicy
        if EngagementPolicy.can_view_full_phone(user, self.contact_list):
            return self.phone_raw
        return self.phone_masked


# ── Call Log ──────────────────────────────────────────────────────────────────

class CallLog(models.Model):
    """Lịch sử mỗi lần gọi / liên hệ với contact."""

    class Outcome(models.TextChoices):
        NO_ANSWER      = "NO_ANSWER",      "Không bắt máy"
        BUSY           = "BUSY",           "Máy bận"
        WRONG_NUMBER   = "WRONG_NUMBER",   "Sai số"
        REACHED        = "REACHED",        "Liên hệ được"
        INTERESTED     = "INTERESTED",     "Quan tâm"
        NOT_INTERESTED = "NOT_INTERESTED", "Không quan tâm"
        CALLBACK       = "CALLBACK",       "Hẹn gọi lại"
        CONVERTED      = "CONVERTED",      "Đã chốt"
        DO_NOT_CALL    = "DO_NOT_CALL",    "Yêu cầu không gọi"

    class Channel(models.TextChoices):
        PHONE     = "PHONE",     "Điện thoại"
        ZALO      = "ZALO",      "Zalo"
        MESSENGER = "MESSENGER", "Messenger"
        EMAIL     = "EMAIL",     "Email"
        OTHER     = "OTHER",     "Khác"

    contact    = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name="call_logs")
    agent      = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name="engagement_call_logs",
    )
    channel    = models.CharField(max_length=12, choices=Channel.choices, default=Channel.PHONE)
    outcome    = models.CharField(max_length=20, choices=Outcome.choices)
    duration_s = models.PositiveIntegerField(default=0, verbose_name="Thời lượng (giây)")
    note       = models.TextField(blank=True, verbose_name="Ghi chú cuộc gọi")
    follow_up_at = models.DateTimeField(null=True, blank=True, verbose_name="Hẹn follow-up")
    called_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "engagement_call_log"
        ordering = ["-called_at"]
        verbose_name = "Lịch sử liên hệ"
