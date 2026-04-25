from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.ai_assistant.knowledge_services import (
    SourceDocument,
    build_knowledge_context,
    split_text_into_chunks,
    sync_knowledge_index,
)
from apps.ai_assistant.models import KnowledgeChunk, KnowledgeDocument
from apps.ai_assistant.services import build_messages_payload


class KnowledgeServicesTests(TestCase):
    def test_sync_knowledge_index_creates_documents_and_chunks(self):
        with (
            patch(
                "apps.ai_assistant.knowledge_services.list_source_documents",
                return_value=[
                    SourceDocument(
                        source_type=KnowledgeDocument.SOURCE_PROCEDURE,
                        source_id=101,
                        title="Quy trình khám tổng quát",
                        content="Mở hồ sơ\nTiếp nhận khách\nThực hiện khám",
                        metadata={"category": "operations"},
                    )
                ],
            ),
            patch(
                "apps.ai_assistant.knowledge_services.embed_texts",
                side_effect=lambda texts: [[0.1, 0.2, 0.3] for _ in texts],
            ),
        ):
            stats = sync_knowledge_index()

        self.assertEqual(stats["indexed_documents"], 1)
        self.assertEqual(KnowledgeDocument.records.count(), 1)
        self.assertGreaterEqual(KnowledgeChunk.records.count(), 1)

    def test_split_text_into_chunks_splits_long_text(self):
        text = "\n".join([f"Đoạn {index} " + ("x" * 120) for index in range(20)])

        chunks = split_text_into_chunks(text, max_chars=300, overlap_chars=40)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= 300 for chunk in chunks))

    def test_build_knowledge_context_filters_sources_by_user_permissions(self):
        user = get_user_model().objects.create_user(username="staff", password="secret")

        document_procedure = KnowledgeDocument.records.create(
            source_type=KnowledgeDocument.SOURCE_PROCEDURE,
            source_id=1,
            title="Quy trình A",
            content="Quy trình nội bộ",
            metadata={},
            content_hash="hash-procedure",
        )
        KnowledgeChunk.records.create(
            document=document_procedure,
            chunk_index=0,
            content="Quy trình tiếp nhận khách hàng doanh nghiệp.",
            metadata={},
            content_hash="chunk-procedure",
            embedding=[1.0, 0.0],
            char_count=40,
        )

        document_category = KnowledgeDocument.records.create(
            source_type=KnowledgeDocument.SOURCE_CATEGORY,
            source_id=2,
            title="Danh mục B",
            content="Danh mục khám",
            metadata={},
            content_hash="hash-category",
        )
        KnowledgeChunk.records.create(
            document=document_category,
            chunk_index=0,
            content="Danh mục xét nghiệm huyết học.",
            metadata={},
            content_hash="chunk-category",
            embedding=[1.0, 0.0],
            char_count=30,
        )

        with patch(
            "apps.ai_assistant.knowledge_services.embed_texts",
            side_effect=lambda texts: [[1.0, 0.0] for _ in texts],
        ):
            context = build_knowledge_context("quy trình tiếp nhận", user=user)

        self.assertIn("Quy trình A", context)
        self.assertNotIn("Danh mục B", context)

    def test_build_messages_payload_includes_knowledge_context(self):
        payload = build_messages_payload([], knowledge_context="Nguồn 1: Quy trình A")

        self.assertEqual(len(payload), 2)
        self.assertIn("Nguồn 1: Quy trình A", payload[1]["content"])
