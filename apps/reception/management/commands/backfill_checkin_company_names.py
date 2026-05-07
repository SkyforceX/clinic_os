from __future__ import annotations

from datetime import date

from django.db.models import Q
from django.core.management.base import BaseCommand

from apps.reception.models import CheckInRecord
from apps.reception.services.checkin_backfill import backfill_checkin_company_data


class Command(BaseCommand):
    help = (
        "Backfill company names for check-in records that are blank or marked as "
        "'Khong xac dinh' from HIS package / organization data."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Preview only, do not write to DB.")
        parser.add_argument("--all", action="store_true", dest="force_all", help="Refresh all records, not only unresolved ones.")
        parser.add_argument("--record-id", type=int, help="Only process one CheckInRecord.")
        parser.add_argument("--date-from", type=date.fromisoformat, help="Filter from exam_date YYYY-MM-DD.")
        parser.add_argument("--date-to", type=date.fromisoformat, help="Filter to exam_date YYYY-MM-DD.")

    def handle(self, *args, **options):
        queryset = CheckInRecord.objects.all()

        record_id = options.get("record_id")
        if record_id:
            queryset = queryset.filter(pk=record_id)

        date_from = options.get("date_from")
        if date_from:
            queryset = queryset.filter(exam_date__gte=date_from)

        date_to = options.get("date_to")
        if date_to:
            queryset = queryset.filter(exam_date__lte=date_to)

        if not options.get("force_all"):
            queryset = queryset.filter(
                Q(snapshot_company_name="")
                | Q(snapshot_company_name__iexact="Không xác định")
                | Q(snapshot_company_name__iexact="Khong xac dinh")
                | Q(snapshot_company_name__iexact="unknown")
            )

        result = backfill_checkin_company_data(
            queryset=queryset,
            dry_run=bool(options.get("dry_run")),
            force_all=bool(options.get("force_all")),
        )

        mode = "DRY RUN" if options.get("dry_run") else "APPLY"
        self.stdout.write(self.style.SUCCESS(f"[{mode}] Check-in company backfill completed."))
        self.stdout.write(f"- scanned: {result.scanned}")
        self.stdout.write(f"- updated: {result.updated}")
        self.stdout.write(f"- unchanged: {result.unchanged}")
        self.stdout.write(f"- unresolved: {result.unresolved}")
