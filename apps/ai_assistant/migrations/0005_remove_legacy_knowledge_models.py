from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("ai_assistant", "0004_pgvector_embedding_ann"),
        ("ai_knowledge", "0002_import_legacy_ai_assistant_knowledge"),
    ]

    operations = [
        migrations.DeleteModel(
            name="KnowledgeChunk",
        ),
        migrations.DeleteModel(
            name="KnowledgeDocument",
        ),
    ]
