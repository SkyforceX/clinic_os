from __future__ import annotations

import textwrap

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.procedures.services.procedure_seed_services import (
    SEEDED_PROCEDURE_CODES,
    seed_clinic_os_usage_procedures,
)


class Command(BaseCommand):
    help = textwrap.dedent(
        """\
        Seed bo quy trinh huong dan su dung clinic_os vao DB procedures.
        Command an toan de chay nhieu lan: se update lai cac quy trinh seed theo code co dinh
        va rebuild cay buoc cho dung phien ban hien tai.
        """
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--creator-username",
            default="",
            help="Username nguoi tao muon gan cho cac procedure seed. Neu bo trong se tu chon admin/staff dau tien.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Xem truoc thay doi, khong luu database.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        verbosity = options["verbosity"]
        creator = self._resolve_creator(options.get("creator_username") or "")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY-RUN mode: cac thay doi se duoc rollback.\n"))

        with transaction.atomic():
            result = seed_clinic_os_usage_procedures(created_by=creator)

            if verbosity >= 1:
                creator_label = creator.username if creator else "NULL"
                self.stdout.write(self.style.SUCCESS("Seed quy trinh clinic_os hoan tat tam thoi trong transaction."))
                self.stdout.write(f"  Nguoi tao gan vao du lieu: {creator_label}")
                self.stdout.write(f"  Tao moi quy trinh      : {result['created_count']}")
                self.stdout.write(f"  Cap nhat quy trinh     : {result['updated_count']}")
                self.stdout.write(f"  Tong so buoc da seed   : {result['step_count']}")

            if verbosity >= 2:
                self.stdout.write("\nDanh sach ma quy trinh duoc quan ly boi command:")
                for code in result["procedure_codes"]:
                    self.stdout.write(f"  - {code}")

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write("\n" + "-" * 68)
        self.stdout.write(self.style.HTTP_INFO("Command: python manage.py seed_clinic_os_usage_procedures"))
        self.stdout.write(self.style.HTTP_INFO(f"Managed codes: {', '.join(SEEDED_PROCEDURE_CODES)}"))
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY-RUN da rollback toan bo thay doi."))
        else:
            self.stdout.write(self.style.SUCCESS("Du lieu quy trinh su dung clinic_os da san sang trong module Procedures."))

    @staticmethod
    def _resolve_creator(username: str):
        user_model = get_user_model()

        if username:
            return user_model.objects.filter(username=username).first()

        creator = user_model.objects.filter(is_superuser=True).order_by("id").first()
        if creator:
            return creator

        creator = user_model.objects.filter(is_staff=True).order_by("id").first()
        if creator:
            return creator

        return user_model.objects.order_by("id").first()
