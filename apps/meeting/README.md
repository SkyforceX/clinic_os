# apps/meeting — Phòng họp liên phòng ban

## Tổng quan

App quản lý buổi họp liên phòng ban để triển khai kế hoạch KSK.
Thay thế file Excel trong phòng họp bằng màn hình collaborative — tất cả
thành viên cùng chỉnh trực tiếp. Đầu ra: biên bản ký số + tasks tự động.

```
meeting_session
  └── meeting_participant      (ai tham dự, quyền chỉnh sửa)
  └── dept_assignment          (phân công từng phòng ban)
        └── staff_shift        (nhân viên + ca sáng/chiều)
  └── meeting_commitment       (cam kết → auto tạo tasks.Task)
  └── meeting_signature        (chữ ký số SHA-256)
```

## Cài đặt vào clinic_os

### 1. Thêm vào INSTALLED_APPS (settings.py)

```python
INSTALLED_APPS = [
    ...
    "apps.meeting",
    "apps.tasks",      # cần có trước khi chạy migration 0002
    ...
]
```

### 2. Thêm URL (clinic_os/urls.py)

```python
from django.urls import include, path

urlpatterns = [
    ...
    path("meeting/", include("apps.meeting.urls", namespace="meeting")),
    ...
]
```

### 3. Migrate theo thứ tự

```bash
# Bước 1: migrate meeting (không cần tasks)
python manage.py migrate meeting 0001

# Bước 2: migrate tasks app (khi tasks app đã có)
python manage.py migrate tasks

# Bước 3: thêm FK meeting → tasks
python manage.py migrate meeting 0002
```

### 4. Tạo Groups nếu chưa có

```python
from django.contrib.auth.models import Group
Group.objects.get_or_create(name="Manager")
Group.objects.get_or_create(name="Managers")
```

## Cấu trúc file

```
apps/meeting/
├── apps.py
├── admin.py
├── policies.py          # MeetingPolicy — Group-based auth
├── urls.py
├── domain/
│   ├── enums.py         # MeetingStatus, ShiftType, CommitmentStatus,...
│   └── exceptions.py    # MeetingDomainError và các subclass
├── models/
│   ├── session.py       # MeetingSession, MeetingParticipant
│   ├── assignment.py    # DeptAssignment, StaffShift
│   └── commitment.py    # MeetingCommitment, MeetingSignature
├── selectors/
│   ├── session_selectors.py
│   └── commitment_selectors.py
├── services/
│   ├── create_session.py       # CreateSessionCommand + execute()
│   ├── manage_session.py       # advance_step, confirm_dept, close_session
│   ├── manage_commitments.py   # add/update/delete commitment
│   ├── create_tasks.py         # bridge: meeting → tasks
│   └── sign_minutes.py         # chữ ký số + verify
├── migrations/
│   ├── 0001_initial.py
│   └── 0002_add_task_fk.py     # chạy sau tasks migrate
└── web/views/
    ├── session_views.py
    ├── dept_views.py
    ├── commitment_views.py
    └── sign_views.py
```

## Luồng nghiệp vụ chính

```
1. create_session()          → MeetingSession (OPEN, step=1)
2. add_staff_shift()         → StaffShift per nhân viên
3. confirm_dept_assignment() → DeptAssignment.confirmed = True
4. advance_step()            → current_step 1→2→3→4→5
5. add_commitment()          → MeetingCommitment
6. close_session()           → status CLOSED
                             → create_tasks_from_session() tự động
7. sign_meeting_minutes()    → MeetingSignature (SHA-256 hash)
                             → status SIGNED khi đủ chữ ký LEAD
```

## Dependency graph

```
meeting → contract.Contract       (nullable FK)
meeting → organizations.Company   (nullable FK)
meeting → AUTH_USER_MODEL
meeting → tasks.Task              (MeetingCommitment.task, 0002)
```

## Chú ý khi mở rộng

- **Thêm phòng ban mới**: sửa `DEPARTMENT_CHOICES` trong `domain/enums.py`
- **Thêm bước họp**: tăng `MEETING_STEP_MAX` và `MEETING_STEP_LABELS`
- **PDF biên bản**: cài `weasyprint`, tạo template `meeting/staff/minutes_pdf.html`
- **Notification**: implement `_send_signed_notification()` trong `sign_minutes.py`
