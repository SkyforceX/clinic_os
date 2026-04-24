from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Deprecated: dữ liệu khám chuyên sâu hiện đọc từ his_integration, "
        "không còn sửa dữ liệu app patients local."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Giữ tương thích tham số cũ; command không còn ghi dữ liệu.",
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.WARNING(
                "Command này đã dừng hoạt động vì clinical dùng dữ liệu HIS sync. "
                "Nếu cần sửa dữ liệu mẫu, hãy sửa nguồn JSON/HIS sync rồi đồng bộ lại."
            )
        )
