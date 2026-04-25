from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("ai_assistant", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="KnowledgeDocument",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_type", models.CharField(choices=[("procedure", "Quy trình"), ("checkup_category", "Danh mục khám"), ("checkup_package", "Gói khám mẫu")], max_length=32)),
                ("source_id", models.PositiveIntegerField()),
                ("title", models.CharField(max_length=255)),
                ("content", models.TextField()),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("content_hash", models.CharField(max_length=64)),
                ("is_active", models.BooleanField(default=True)),
                ("source_updated_at", models.DateTimeField(blank=True, null=True)),
                ("last_indexed_at", models.DateTimeField(auto_now=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Tài liệu tri thức AI",
                "verbose_name_plural": "Tài liệu tri thức AI",
                "ordering": ["source_type", "source_id"],
            },
        ),
        migrations.CreateModel(
            name="KnowledgeChunk",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("chunk_index", models.PositiveIntegerField()),
                ("content", models.TextField()),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("content_hash", models.CharField(max_length=64)),
                ("embedding", models.JSONField(blank=True, default=list)),
                ("char_count", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("document", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="chunks", to="ai_assistant.knowledgedocument")),
            ],
            options={
                "verbose_name": "Đoạn tri thức AI",
                "verbose_name_plural": "Đoạn tri thức AI",
                "ordering": ["document_id", "chunk_index"],
            },
        ),
        migrations.AddConstraint(
            model_name="knowledgedocument",
            constraint=models.UniqueConstraint(fields=("source_type", "source_id"), name="uq_ai_knowledge_source"),
        ),
        migrations.AddConstraint(
            model_name="knowledgechunk",
            constraint=models.UniqueConstraint(fields=("document", "chunk_index"), name="uq_ai_knowledge_chunk_per_doc"),
        ),
    ]
