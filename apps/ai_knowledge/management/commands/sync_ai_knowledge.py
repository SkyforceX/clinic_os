from django.core.management.base import BaseCommand, CommandError

from apps.ai_knowledge.services.extractors import SUPPORTED_SOURCE_TYPES
from apps.ai_knowledge.services.indexing import sync_knowledge_index


class Command(BaseCommand):
    help = "Sync all supported AI knowledge sources based on extractor mapping."

    def add_arguments(self, parser):
        parser.add_argument("--source-type", action="append", dest="source_types")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--force", action="store_true")

    def handle(self, *args, **options):
        requested_source_types = options.get("source_types") or list(SUPPORTED_SOURCE_TYPES)
        invalid_source_types = [
            source_type for source_type in requested_source_types
            if source_type not in SUPPORTED_SOURCE_TYPES
        ]
        if invalid_source_types:
            raise CommandError(
                f"Unsupported source types: {', '.join(sorted(invalid_source_types))}"
            )

        stats = sync_knowledge_index(
            source_types=requested_source_types,
            force=bool(options.get("force")),
            dry_run=bool(options.get("dry_run")),
        )
        self.stdout.write(self.style.SUCCESS("AI knowledge sync completed."))
        self.stdout.write(
            "total_source_documents={total_source_documents} indexed_documents={indexed_documents} "
            "indexed_chunks={indexed_chunks} skipped_documents={skipped_documents} "
            "failed_documents={failed_documents} deactivated_documents={deactivated_documents}".format(**stats)
        )
