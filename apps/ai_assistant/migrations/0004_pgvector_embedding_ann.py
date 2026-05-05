from django.db import migrations

import apps.ai_assistant.fields


class Migration(migrations.Migration):

    dependencies = [
        ("ai_assistant", "0003_alter_knowledgechunk_managers_and_more"),
    ]

    operations = [
        migrations.RunSQL(
            sql="CREATE EXTENSION IF NOT EXISTS vector",
            reverse_sql="",
        ),
        migrations.AddField(
            model_name="knowledgechunk",
            name="embedding_vector",
            field=apps.ai_assistant.fields.VectorField(
                blank=True,
                null=True,
                dimensions=768,
            ),
        ),
        migrations.RunSQL(
            sql="""
                UPDATE ai_assistant_knowledgechunk
                SET embedding_vector = (
                    (
                        '[' || COALESCE(
                            (
                                SELECT string_agg(value, ',')
                                FROM jsonb_array_elements_text(embedding) AS value
                            ),
                            ''
                        ) || ']'
                    )::vector
                )
                WHERE jsonb_typeof(embedding) = 'array'
                  AND jsonb_array_length(embedding) > 0
            """,
            reverse_sql="""
                UPDATE ai_assistant_knowledgechunk
                SET embedding_vector = NULL
            """,
        ),
        migrations.RunSQL(
            sql="""
                DO $$
                BEGIN
                    IF EXISTS (SELECT 1 FROM pg_am WHERE amname = 'hnsw') THEN
                        EXECUTE '
                            CREATE INDEX IF NOT EXISTS ai_assistant_kc_embedding_ann
                            ON ai_assistant_knowledgechunk
                            USING hnsw (embedding_vector vector_cosine_ops)
                        ';
                    ELSE
                        EXECUTE '
                            CREATE INDEX IF NOT EXISTS ai_assistant_kc_embedding_ann
                            ON ai_assistant_knowledgechunk
                            USING ivfflat (embedding_vector vector_cosine_ops)
                            WITH (lists = 100)
                        ';
                    END IF;
                END
                $$;
            """,
            reverse_sql="""
                DROP INDEX IF EXISTS ai_assistant_kc_embedding_ann
            """,
        ),
    ]
