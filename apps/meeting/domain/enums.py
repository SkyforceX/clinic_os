from enum import Enum


class MeetingStatus(str, Enum):
    OPEN = "OPEN"          # Đang diễn ra / đang soạn
    CLOSED = "CLOSED"      # Đã kết thúc, chờ ký
    SIGNED = "SIGNED"      # Biên bản đã ký đầy đủ
    CANCELLED = "CANCELLED"

    @classmethod
    def active_statuses(cls):
        return (cls.OPEN, cls.CLOSED)


class ParticipantRole(str, Enum):
    LEAD = "LEAD"        # Người điều hành / trưởng phòng đại diện
    MEMBER = "MEMBER"    # Thành viên tham dự
    VIEWER = "VIEWER"    # Chỉ xem (không chỉnh)


class ShiftType(str, Enum):
    AM = "AM"      # Ca sáng
    PM = "PM"      # Ca chiều
    FULL = "FULL"  # Cả ngày
    OFF = "OFF"    # Nghỉ / không tham gia


class CommitmentStatus(str, Enum):
    OPEN = "OPEN"
    DONE = "DONE"
    CANCELLED = "CANCELLED"


# Danh sách phòng ban mặc định — admin có thể mở rộng
DEPARTMENT_CHOICES = [
    ("kd", "Kinh doanh"),
    ("dd", "Điều dưỡng / Lâm sàng"),
    ("hc", "Hành chính / Vận hành"),
    ("kt", "Kế toán / Tài chính"),
    ("it", "IT / Hệ thống"),
    ("other", "Khác"),
]

MEETING_STEP_LABELS = {
    1: "Xác nhận thông tin ngày KSK",
    2: "Phân công nhân sự",
    3: "Lịch trình & ca làm việc",
    4: "Nghiệp vụ & Vật tư",
    5: "Cam kết & Ký biên bản",
}
MEETING_STEP_MAX = 5
