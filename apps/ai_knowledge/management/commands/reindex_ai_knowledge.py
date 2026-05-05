from django.core.management.base import BaseCommand, CommandError

from apps.ai_knowledge.models import AIKnowledgeSource
from apps.ai_knowledge.services.extractors import SUPPORTED_SOURCE_TYPES
from apps.ai_knowledge.services.indexing import index_all_by_source_type, reindex_source


class Command(BaseCommand):
    help = "Force reindex AI knowledge sources."

    def add_arguments(self, parser):
        parser.add_argument("--source-type", required=True)
        parser.add_argument("--id")
        parser.add_argument("--all", action="store_true")
        parser.add_argument("--force", action="store_true")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        source_type = options["source_type"]
        valid_source_types = set(SUPPORTED_SOURCE_TYPES)
        if source_type not in valid_source_types:
            raise CommandError(f"Unsupported source type: {source_type}")

        source_id = options.get("id")
        reindex_all = options.get("all")
        dry_run = options.get("dry_run", False)
        force = bool(options.get("force", False) or source_id or reindex_all)

        if not source_id and not reindex_all:
            raise CommandError("Provide --id or --all.")
        if source_id and reindex_all:
            raise CommandError("Use either --id or --all, not both.")

        if reindex_all:
            stats = index_all_by_source_type(
                source_type=source_type,
                force=force,
                dry_run=dry_run,
            )
            self.stdout.write(self.style.SUCCESS("AI knowledge reindex completed."))
            self.stdout.write(
                f"total={stats['total']} indexed={stats['indexed']} skipped={stats['skipped']} failed={stats['failed']} chunks={stats['chunks']}"
            )
            return

        try:
            result = reindex_source(
                source_type=source_type,
                source_id=source_id,
                force=force,
                dry_run=dry_run,
            )
        except Exception as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS("AI knowledge source reindexed."))
        self.stdout.write(str(result))
