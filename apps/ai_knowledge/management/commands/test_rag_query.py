from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.ai_knowledge.services.retrieval import retrieve_context_for_question


class Command(BaseCommand):
    help = "Run a local RAG query against indexed AI knowledge."

    def add_arguments(self, parser):
        parser.add_argument("question")
        parser.add_argument("--username")
        parser.add_argument("--source-type", action="append", dest="source_types")
        parser.add_argument("--top-k", type=int, default=5)

    def handle(self, *args, **options):
        username = options.get("username")
        if username:
            user = get_user_model().objects.filter(username=username).first()
            if user is None:
                raise CommandError(f"User not found: {username}")
        else:
            user = get_user_model()()

        results = retrieve_context_for_question(
            user=user,
            question=options["question"],
            source_types=options.get("source_types"),
            top_k=options["top_k"],
        )
        self.stdout.write(self.style.SUCCESS(f"Retrieved {len(results)} chunks."))
        for item in results:
            self.stdout.write(
                f"[{item['source_type']}:{item['source_id']}] #{item['chunk_index']} score={item['similarity']:.3f}"
            )
            self.stdout.write(item["content"][:240])
