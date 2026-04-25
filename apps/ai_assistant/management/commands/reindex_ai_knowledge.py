from django.core.management.base import BaseCommand, CommandError

from apps.ai_assistant.knowledge_services import sync_knowledge_index
from apps.ai_assistant.models import KnowledgeDocument


class Command(BaseCommand):
    help = "Tạo hoặc cập nhật knowledge index cho AI assistant."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            action="append",
            choices=[choice for choice, _ in KnowledgeDocument.SOURCE_CHOICES],
            help="Chỉ reindex một hoặc nhiều nguồn cụ thể.",
        )

    def handle(self, *args, **options):
        source_types = options.get("source") or None

        try:
            stats = sync_knowledge_index(source_types=source_types)
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS("Đã cập nhật knowledge index cho AI assistant."))
        self.stdout.write(f"- Tổng tài liệu nguồn: {stats['total_source_documents']}")
        self.stdout.write(f"- Tài liệu reindex: {stats['indexed_documents']}")
        self.stdout.write(f"- Chunk tạo mới: {stats['indexed_chunks']}")
        self.stdout.write(f"- Tài liệu bị vô hiệu hóa: {stats['deactivated_documents']}")
