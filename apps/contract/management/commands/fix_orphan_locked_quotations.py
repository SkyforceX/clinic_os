from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from apps.contract.models import QuotationDraft


class Command(BaseCommand):
    help = (
        "Sửa dữ liệu báo giá bị khóa nhưng không còn hợp đồng liên kết. "
        "Mặc định chạy dry-run, thêm --apply để ghi DB."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            dest="apply",
            help="Thực sự cập nhật dữ liệu vào DB.",
        )
        parser.add_argument(
            "--quotation-id",
            type=int,
            default=None,
            help="Chỉ sửa 1 báo giá theo ID.",
        )

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        quotation_id = options.get("quotation_id")

        qs = (
            QuotationDraft.objects
            .select_related("locked_by", "corporate_contract_profile__contract")
            .filter(is_locked=True)
        )

        if quotation_id:
            qs = qs.filter(pk=quotation_id)

        candidates = []
        for quotation in qs:
            profile = getattr(quotation, "corporate_contract_profile", None)
            linked_contract = getattr(profile, "contract", None) if profile else None

            # Sai dữ liệu: báo giá đang locked nhưng không còn contract thực tế
            if linked_contract is None:
                candidates.append((quotation, profile))

        if not candidates:
            self.stdout.write(self.style.SUCCESS("Không có báo giá lỗi cần sửa."))
            return

        self.stdout.write(
            self.style.WARNING(
                f"Phát hiện {len(candidates)} báo giá bị khóa sai trạng thái."
            )
        )

        for quotation, profile in candidates:
            profile_id = getattr(profile, "id", None)
            self.stdout.write(
                f"- Quotation #{quotation.pk} | company={quotation.company_name!r} "
                f"| profile_id={profile_id} | locked_by={getattr(quotation.locked_by, 'username', None)}"
            )

        if not apply_changes:
            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING(
                    "Đang ở chế độ dry-run. Chưa có thay đổi nào được ghi."
                )
            )
            self.stdout.write(
                "Chạy lại với: python manage.py fix_orphan_locked_quotations --apply"
            )
            return

        fixed_count = 0
        detached_profile_count = 0

        with transaction.atomic():
            for quotation, profile in candidates:
                # Nếu còn corporate profile mồ côi thì gỡ luôn liên kết quotation
                if profile is not None and getattr(profile, "quotation_id", None) == quotation.id:
                    profile.quotation = None
                    profile.save(update_fields=["quotation", "updated_at"])
                    detached_profile_count += 1

                quotation.is_locked = False
                quotation.locked_at = None
                quotation.locked_by = None
                quotation.save(update_fields=["is_locked", "locked_at", "locked_by", "updated_at"])
                fixed_count += 1

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Đã sửa {fixed_count} báo giá; gỡ liên kết {detached_profile_count} corporate profile mồ côi."
            )
        )