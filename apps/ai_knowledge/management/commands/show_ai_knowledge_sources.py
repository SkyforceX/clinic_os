from collections import Counter

from django.core.management.base import BaseCommand, CommandError

from apps.ai_knowledge.services.extractors import SUPPORTED_SOURCE_TYPES, list_source_documents


class Command(BaseCommand):
    help = "Show diagnostic information about AI knowledge source documents produced by extractors."

    def add_arguments(self, parser):
        parser.add_argument("--source-type", action="append", dest="source_types")
        parser.add_argument("--sample", type=int, default=3)

    def handle(self, *args, **options):
        requested_source_types = options.get("source_types") or list(SUPPORTED_SOURCE_TYPES)
        invalid_source_types = [
            source_type
            for source_type in requested_source_types
            if source_type not in SUPPORTED_SOURCE_TYPES
        ]
        if invalid_source_types:
            raise CommandError(
                f"Unsupported source types: {', '.join(sorted(invalid_source_types))}"
            )

        sample_size = max(0, int(options.get("sample") or 0))
        grand_total = 0

        for source_type in requested_source_types:
            try:
                documents = list_source_documents(source_types=[source_type])
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f"[{source_type}] error: {exc}"))
                continue

            grand_total += len(documents)
            access_counter = Counter(item.access_level for item in documents)
            self.stdout.write(
                self.style.SUCCESS(
                    f"[{source_type}] total={len(documents)} access_levels={dict(access_counter)}"
                )
            )

            if not documents:
                self.stdout.write("  no source documents produced")
                continue

            for item in documents[:sample_size]:
                metadata_keys = ", ".join(sorted((item.metadata or {}).keys())[:8])
                self.stdout.write(
                    f"  - id={item.source_id} access={item.access_level} title={item.title}"
                )
                if metadata_keys:
                    self.stdout.write(f"    metadata_keys={metadata_keys}")

        self.stdout.write(self.style.SUCCESS(f"grand_total={grand_total}"))
