from django.core.management.base import BaseCommand
from django.db import transaction

from apps.catalogs.models import CheckupCategory, CheckupPackageTemplate, GroupCheckup


class Command(BaseCommand):
    help = "Xóa toàn bộ danh mục khám, nhóm khám và gói khám mẫu."

    @transaction.atomic
    def handle(self, *args, **options):
        CheckupPackageTemplate.objects.all().delete()
        CheckupCategory.objects.all().delete()
        GroupCheckup.objects.all().delete()
        self.stdout.write(self.style.SUCCESS("Đã xóa toàn bộ dữ liệu catalog và package templates."))