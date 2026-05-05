from django.core.management.base import BaseCommand, CommandError

from apps.ai_knowledge.models import AIKnowledgeSource
from apps.ai_knowledge.services.extractors import SUPPORTED_SOURCE_TYPES
from apps.ai_knowledge.services.indexing import index_all_by_source_type, index_source


class Command(BaseCommand):
    help = "Index AI knowledge sources into pgvector-backed chunks."

    def add_arguments(self, parser):
        parser.add_argument("--source-type", required=True)
        parser.add_argument("--id")
        parser.add_argument("--all", action="store_true")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        source_type = options["source_type"]
        valid_source_types = set(SUPPORTED_SOURCE_TYPES)
        if source_type not in valid_source_types:
            raise CommandError(f"Unsupported source type: {source_type}")

        source_id = options.get("id")
        index_all = options.get("all")
        dry_run = options.get("dry_run", False)
        if not source_id and not index_all:
            raise CommandError("Provide --id or --all.")

        if source_id and index_all:
            raise CommandError("Use either --id or --all, not both.")

        if index_all:
            stats = index_all_by_source_type(
                source_type=source_type,
                dry_run=dry_run,
            )
            self.stdout.write(self.style.SUCCESS("AI knowledge indexing completed."))
            self.stdout.write(
                f"total={stats['total']} indexed={stats['indexed']} skipped={stats['skipped']} failed={stats['failed']} chunks={stats['chunks']}"
            )
            return

        try:
            result = index_source(
                source_type=source_type,
                source_id=source_id,
                dry_run=dry_run,
            )
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS("AI knowledge source processed."))
        self.stdout.write(str(result))
