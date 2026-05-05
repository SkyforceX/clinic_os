from django.db import migrations, models
import django.db.models.deletion

import apps.ai_knowledge.fields


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.RunSQL(
            sql="CREATE EXTENSION IF NOT EXISTS vector",
            reverse_sql="",
        ),
        migrations.CreateModel(
            name="AIKnowledgeSource",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_type", models.CharField(choices=[("procedure", "Procedure"), ("checkup_category", "Checkup Category"), ("checkup_package", "Checkup Package"), ("page", "Page"), ("post", "Post"), ("faq", "FAQ"), ("service", "Service"), ("contract", "Contract"), ("quotation", "Quotation"), ("policy", "Policy"), ("patient_summary", "Patient Summary"), ("visit_summary", "Visit Summary"), ("clinical_note", "Clinical Note"), ("medical_record", "Medical Record"), ("document", "Document"), ("internal_note", "Internal Note")], max_length=32)),
                ("source_id", models.CharField(max_length=64)),
                ("title", models.CharField(max_length=255)),
                ("source_url", models.CharField(blank=True, max_length=500)),
                ("locale", models.CharField(default="vi", max_length=16)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("indexed", "Indexed"), ("stale", "Stale"), ("failed", "Failed"), ("disabled", "Disabled")], default="pending", max_length=16)),
                ("content_hash", models.CharField(blank=True, max_length=64)),
                ("indexed_at", models.DateTimeField(blank=True, null=True)),
                ("last_error", models.TextField(blank=True)),
                ("access_level", models.CharField(choices=[("public", "Public"), ("internal", "Internal"), ("manager", "Manager"), ("contract", "Contract"), ("clinical", "Clinical"), ("patient", "Patient"), ("admin", "Admin")], default="internal", max_length=16)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["source_type", "source_id"]},
        ),
        migrations.CreateModel(
            name="AIKnowledgeChunk",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_type", models.CharField(max_length=32)),
                ("source_id", models.CharField(max_length=64)),
                ("section_key", models.CharField(blank=True, max_length=128)),
                ("chunk_index", models.PositiveIntegerField()),
                ("title", models.CharField(blank=True, max_length=255)),
                ("section_title", models.CharField(blank=True, max_length=255)),
                ("content", models.TextField()),
                ("embedding", apps.ai_knowledge.fields.VectorField(blank=True, dimensions=768, null=True)),
                ("embedding_model", models.CharField(blank=True, max_length=128)),
                ("embedding_dim", models.PositiveIntegerField(default=768)),
                ("token_count", models.PositiveIntegerField(default=0)),
                ("prev_chunk_index", models.PositiveIntegerField(blank=True, null=True)),
                ("next_chunk_index", models.PositiveIntegerField(blank=True, null=True)),
                ("access_level", models.CharField(choices=[("public", "Public"), ("internal", "Internal"), ("manager", "Manager"), ("contract", "Contract"), ("clinical", "Clinical"), ("patient", "Patient"), ("admin", "Admin")], default="internal", max_length=16)),
                ("locale", models.CharField(default="vi", max_length=16)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("indexed", "Indexed"), ("stale", "Stale"), ("failed", "Failed"), ("disabled", "Disabled")], default="indexed", max_length=16)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("source_record", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="chunks", to="ai_knowledge.aiknowledgesource")),
            ],
            options={"ordering": ["source_id", "section_key", "chunk_index"]},
        ),
        migrations.AddConstraint(
            model_name="aiknowledgesource",
            constraint=models.UniqueConstraint(fields=("source_type", "source_id"), name="uq_ai_knowledge_source_type_id"),
        ),
        migrations.AddConstraint(
            model_name="aiknowledgechunk",
            constraint=models.UniqueConstraint(fields=("source_record", "chunk_index"), name="uq_ai_knowledge_chunk_source_idx"),
        ),
        migrations.AddIndex(model_name="aiknowledgesource", index=models.Index(fields=["source_type"], name="ai_kn_src_type_idx")),
        migrations.AddIndex(model_name="aiknowledgesource", index=models.Index(fields=["status"], name="ai_kn_src_status_idx")),
        migrations.AddIndex(model_name="aiknowledgesource", index=models.Index(fields=["access_level"], name="ai_kn_src_access_idx")),
        migrations.AddIndex(model_name="aiknowledgesource", index=models.Index(fields=["locale"], name="ai_kn_src_locale_idx")),
        migrations.AddIndex(model_name="aiknowledgechunk", index=models.Index(fields=["source_type"], name="ai_kn_chunk_type_idx")),
        migrations.AddIndex(model_name="aiknowledgechunk", index=models.Index(fields=["source_id"], name="ai_kn_chunk_srcid_idx")),
        migrations.AddIndex(model_name="aiknowledgechunk", index=models.Index(fields=["access_level"], name="ai_kn_chunk_access_idx")),
        migrations.AddIndex(model_name="aiknowledgechunk", index=models.Index(fields=["locale"], name="ai_kn_chunk_locale_idx")),
        migrations.AddIndex(model_name="aiknowledgechunk", index=models.Index(fields=["status"], name="ai_kn_chunk_status_idx")),
        migrations.AddIndex(model_name="aiknowledgechunk", index=models.Index(fields=["section_key"], name="ai_kn_chunk_section_idx")),
        migrations.AddIndex(model_name="aiknowledgechunk", index=models.Index(fields=["chunk_index"], name="ai_kn_chunk_order_idx")),
        migrations.AddIndex(model_name="aiknowledgechunk", index=models.Index(fields=["source_id", "section_key", "chunk_index"], name="ai_kn_chunk_scope_idx")),
        migrations.RunSQL(
            sql=(
                "CREATE INDEX IF NOT EXISTS ai_kn_chunk_embedding_hnsw_idx "
                "ON ai_knowledge_aiknowledgechunk "
                "USING hnsw (embedding vector_cosine_ops)"
            ),
            reverse_sql="DROP INDEX IF EXISTS ai_kn_chunk_embedding_hnsw_idx",
        ),
        migrations.RunSQL(
            sql=(
                "CREATE INDEX IF NOT EXISTS ai_kn_chunk_metadata_gin_idx "
                "ON ai_knowledge_aiknowledgechunk USING gin (metadata)"
            ),
            reverse_sql="DROP INDEX IF EXISTS ai_kn_chunk_metadata_gin_idx",
        ),
    ]
