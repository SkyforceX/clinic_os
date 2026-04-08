"""
apps.hrm.services.account_service
───────────────────────────────────
Quản lý tài khoản hệ thống (Django User) cho nhân viên HRM.

API công khai:
    create_and_link_user(employee, username, password, actor, send_email)
        → User  — tạo mới User, liên kết employee, cấp Group theo chức vụ

    link_existing_user(employee, user, actor)
        → dict  — liên kết User có sẵn, cấp Group theo chức vụ

    unlink_user(employee, actor, deactivate)
        → None  — hủy liên kết, tùy chọn lock tài khoản

    sync_groups_from_position(employee, actor)
        → dict  — đồng bộ lại Group theo PositionGroupMapping hiện tại

    revoke_all_groups(employee, actor)
        → list  — thu hồi toàn bộ Group của user

Mỗi thao tác ghi AccessLog đầy đủ.
"""

from __future__ import annotations

import re
import unicodedata

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
from django.utils.crypto import get_random_string

from apps.hrm.exceptions import HRMPermissionDenied, HRMValidationError
from apps.hrm.models.access_control import AccessLog, AccessLogAction, PositionGroupMapping
from apps.hrm.policies import HRMPolicy

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _log(employee, action, group=None, actor=None, note=""):
    AccessLog.objects.create(
        employee=employee,
        action=action,
        django_group=group,
        actor=actor,
        note=note,
    )


def _slugify_vn(text: str) -> str:
    """Chuyển họ tên tiếng Việt → username dạng ten.nguyen."""
    text = text.lower().strip()
    # Bỏ dấu
    text = text.replace("đ", "d")
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    # Tách từ
    parts = text.split()
    if len(parts) >= 2:
        # ten.ho (họ lấy ký tự đầu mỗi từ phần họ)
        first = parts[-1]
        last_initials = "".join(p[0] for p in parts[:-1])
        slug = f"{first}.{last_initials}"
    else:
        slug = parts[0] if parts else "user"
    # Loại ký tự không hợp lệ
    slug = re.sub(r"[^a-z0-9._]", "", slug)
    return slug


def suggest_username(full_name: str) -> str:
    """
    Gợi ý username từ họ tên. Nếu trùng thì thêm số đuôi.
    VD: "Nguyễn Văn An" → "an.nv"  →  "an.nv2" nếu đã có.
    """
    base = _slugify_vn(full_name) or "user"
    if not User.objects.filter(username=base).exists():
        return base
    i = 2
    while User.objects.filter(username=f"{base}{i}").exists():
        i += 1
    return f"{base}{i}"


def generate_password(length: int = 12) -> str:
    """Sinh password ngẫu nhiên đủ mạnh."""
    return get_random_string(
        length=length,
        allowed_chars="abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789!@#%",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Tạo mới User và liên kết
# ─────────────────────────────────────────────────────────────────────────────

@transaction.atomic
def create_and_link_user(
    *,
    employee,
    username: str,
    password: str,
    actor,
    email: str = "",
) -> User:
    """
    Tạo mới Django User, liên kết với employee,
    cấp Group theo PositionGroupMapping của chức vụ hiện tại.

    Raises HRMValidationError nếu employee đã có user hoặc username trùng.
    """
    if not HRMPolicy.can_grant_access(actor):
        raise HRMPermissionDenied("Bạn không có quyền cấp tài khoản.")

    if employee.user_id:
        raise HRMValidationError(
            f"Nhân viên {employee.full_name} đã có tài khoản "
            f"'{employee.user.username}'."
        )

    username = username.strip().lower()
    if not username:
        raise HRMValidationError("Username không được để trống.")
    if User.objects.filter(username=username).exists():
        raise HRMValidationError(f"Username '{username}' đã tồn tại.")

    # Phân tách first_name / last_name từ full_name
    parts = employee.full_name.strip().split()
    first_name = parts[-1] if parts else ""
    last_name  = " ".join(parts[:-1]) if len(parts) > 1 else ""

    user = User.objects.create_user(
        username=username,
        password=password,
        email=email or employee.email,
        first_name=first_name,
        last_name=last_name,
        is_active=True,
    )

    employee.user = user
    employee.save(update_fields=["user", "updated_at"])

    # Cấp Group theo chức vụ
    granted = _grant_groups(employee=employee, actor=actor)

    _log(
        employee,
        AccessLogAction.GRANTED,
        actor=actor,
        note=(
            f"Tạo tài khoản '{username}' và liên kết. "
            f"Nhóm được cấp: {', '.join(granted) or '(chưa có mapping)'}."
        ),
    )
    return user


# ─────────────────────────────────────────────────────────────────────────────
# Liên kết User có sẵn
# ─────────────────────────────────────────────────────────────────────────────

@transaction.atomic
def link_existing_user(*, employee, user: User, actor, overwrite_groups: bool = True) -> dict:
    """
    Liên kết một Django User đã có với employee.
    overwrite_groups=True → xóa toàn bộ group cũ rồi cấp theo PositionGroupMapping.
    overwrite_groups=False → chỉ ADD group theo mapping, không xóa group cũ.
    """
    if not HRMPolicy.can_grant_access(actor):
        raise HRMPermissionDenied("Bạn không có quyền cấp tài khoản.")

    if employee.user_id and employee.user_id != user.pk:
        raise HRMValidationError(
            f"Nhân viên đã liên kết với tài khoản khác ('{employee.user.username}'). "
            "Hủy liên kết cũ trước."
        )

    # Kiểm tra user chưa bị nhân viên khác dùng
    existing = (
        type(employee).objects
        .filter(user=user)
        .exclude(pk=employee.pk)
        .first()
    )
    if existing:
        raise HRMValidationError(
            f"Tài khoản '{user.username}' đã được liên kết với nhân viên khác: "
            f"{existing.full_name} ({existing.employee_code})."
        )

    employee.user = user
    employee.save(update_fields=["user", "updated_at"])

    if overwrite_groups:
        # Xóa toàn bộ group cũ trước
        old_groups = list(user.groups.all())
        user.groups.clear()
        for g in old_groups:
            _log(employee, AccessLogAction.REVOKED, group=g, actor=actor,
                 note="Xóa group cũ trước khi gán lại theo chức vụ.")

    granted = _grant_groups(employee=employee, actor=actor)

    _log(
        employee,
        AccessLogAction.GRANTED,
        actor=actor,
        note=(
            f"Liên kết tài khoản '{user.username}'. "
            f"Nhóm được cấp: {', '.join(granted) or '(chưa có mapping)'}."
        ),
    )
    return {"username": user.username, "granted": granted}


# ─────────────────────────────────────────────────────────────────────────────
# Hủy liên kết
# ─────────────────────────────────────────────────────────────────────────────

@transaction.atomic
def unlink_user(*, employee, actor, deactivate: bool = False) -> None:
    """
    Hủy liên kết user khỏi employee.
    deactivate=True → set user.is_active = False (dùng khi offboard).
    """
    if not HRMPolicy.can_grant_access(actor):
        raise HRMPermissionDenied("Bạn không có quyền thao tác tài khoản.")

    if not employee.user_id:
        raise HRMValidationError("Nhân viên chưa có tài khoản nào để hủy liên kết.")

    user = employee.user
    username = user.username

    if deactivate:
        user.is_active = False
        user.save(update_fields=["is_active"])

    employee.user = None
    employee.save(update_fields=["user", "updated_at"])

    _log(
        employee,
        AccessLogAction.REVOKED,
        actor=actor,
        note=(
            f"Hủy liên kết tài khoản '{username}'. "
            f"{'Tài khoản đã bị khóa.' if deactivate else 'Tài khoản vẫn hoạt động.'}"
        ),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Đồng bộ Group theo chức vụ
# ─────────────────────────────────────────────────────────────────────────────

@transaction.atomic
def sync_groups_from_position(*, employee, actor) -> dict:
    """
    Thu hồi Group cũ → cấp lại Group theo PositionGroupMapping hiện tại.
    Dùng khi:
      - Cập nhật PositionGroupMapping
      - Nhân viên đổi chức vụ mà không dùng transfer workflow
    """
    if not HRMPolicy.can_grant_access(actor):
        raise HRMPermissionDenied("Bạn không có quyền đồng bộ nhóm quyền.")

    if not employee.user_id:
        raise HRMValidationError(f"{employee.full_name} chưa có tài khoản hệ thống.")

    user = employee.user

    # Thu hồi tất cả group hiện tại
    old_groups = list(user.groups.all())
    user.groups.clear()
    for g in old_groups:
        _log(employee, AccessLogAction.REVOKED, group=g, actor=actor,
             note="Sync: xóa group cũ.")

    # Cấp lại theo mapping
    granted = _grant_groups(employee=employee, actor=actor)

    _log(
        employee,
        AccessLogAction.GRANTED,
        actor=actor,
        note=(
            f"Đồng bộ nhóm quyền theo chức vụ '{employee.position}'. "
            f"Cấp: {', '.join(granted) or '(không có mapping)'}."
        ),
    )
    return {"revoked": [g.name for g in old_groups], "granted": granted}


# ─────────────────────────────────────────────────────────────────────────────
# Thu hồi toàn bộ Group
# ─────────────────────────────────────────────────────────────────────────────

@transaction.atomic
def revoke_all_groups(*, employee, actor) -> list[str]:
    """Thu hồi toàn bộ Django Group của user, giữ nguyên liên kết."""
    if not HRMPolicy.can_grant_access(actor):
        raise HRMPermissionDenied("Bạn không có quyền thu hồi nhóm quyền.")

    if not employee.user_id:
        raise HRMValidationError(f"{employee.full_name} chưa có tài khoản hệ thống.")

    user = employee.user
    groups = list(user.groups.all())
    user.groups.clear()

    for g in groups:
        _log(employee, AccessLogAction.REVOKED, group=g, actor=actor,
             note="Thu hồi toàn bộ nhóm quyền.")

    return [g.name for g in groups]


# ─────────────────────────────────────────────────────────────────────────────
# Internal
# ─────────────────────────────────────────────────────────────────────────────

def _grant_groups(*, employee, actor) -> list[str]:
    """Cấp Group theo PositionGroupMapping của chức vụ hiện tại."""
    if not employee.position or not employee.user_id:
        return []

    mappings = PositionGroupMapping.objects.filter(
        position=employee.position
    ).select_related("django_group")

    granted = []
    for m in mappings:
        employee.user.groups.add(m.django_group)
        _log(
            employee,
            AccessLogAction.GRANTED,
            group=m.django_group,
            actor=actor,
            note=f"Cấp theo mapping chức vụ: {employee.position.name}",
        )
        granted.append(m.django_group.name)

    return granted
