from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase

from apps.ai_knowledge.models import AIKnowledgeChunk, AIKnowledgeSource
from apps.ai_knowledge.services.chunking import create_chunks, split_text_into_chunks
from apps.ai_knowledge.services.extractors import SourceDocument
from apps.ai_knowledge.services.indexing import index_source
from apps.ai_knowledge.services.retrieval import retrieve_context_for_question


def _vector(*active_positions):
    values = [0.0] * 768
    for position, value in active_positions:
        values[position] = value
    return values


class AIKnowledgeChunkingTests(TestCase):
    def test_split_text_into_chunks_keeps_faq_and_bullets_together(self):
        text = "\n".join(
            [
                "Q: Goi kham gom gi?",
                "A: Goi kham gom xet nghiem va chan doan hinh anh.",
                "",
                "- Mau 1",
                "- Mau 2",
                "",
                "Doan van ket thuc.",
            ]
        )

        chunks = split_text_into_chunks(text, max_chars=220, overlap_chars=40)

        self.assertEqual(len(chunks), 1)
        self.assertIn("Q: Goi kham gom gi?", chunks[0])
        self.assertIn("A: Goi kham gom xet nghiem", chunks[0])
        self.assertIn("- Mau 1", chunks[0])
        self.assertIn("- Mau 2", chunks[0])

    def test_create_chunks_sets_prev_next_indices(self):
        text = "\n\n".join([f"Doan {index} " + ("x" * 220) for index in range(4)])

        payloads = create_chunks(text, title="Tai lieu", max_chars=260, overlap_chars=50)

        self.assertGreater(len(payloads), 1)
        self.assertIsNone(payloads[0].prev_chunk_index)
        self.assertEqual(payloads[0].next_chunk_index, 1)
        self.assertEqual(payloads[-1].prev_chunk_index, len(payloads) - 2)
        self.assertIsNone(payloads[-1].next_chunk_index)


class AIKnowledgeIndexingTests(TestCase):
    def test_index_source_creates_source_and_chunks(self):
        with (
            patch(
                "apps.ai_knowledge.services.indexing.extract_text_for_source",
                return_value=SourceDocument(
                    source_type=AIKnowledgeSource.SOURCE_PROCEDURE,
                    source_id="101",
                    title="Quy trinh kham tong quat",
                    content="Mo ho so\nTiep nhan khach\nThuc hien kham",
                    metadata={"category": "operations"},
                ),
            ),
            patch(
                "apps.ai_knowledge.services.indexing.embed_texts",
                side_effect=lambda texts: [_vector((0, 0.1), (1, 0.2)) for _ in texts],
            ),
        ):
            result = index_source(
                source_type=AIKnowledgeSource.SOURCE_PROCEDURE,
                source_id="101",
            )

        self.assertTrue(result["indexed"])
        self.assertEqual(AIKnowledgeSource.objects.count(), 1)
        self.assertGreaterEqual(AIKnowledgeChunk.objects.count(), 1)


class AIKnowledgeRetrievalTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="staff",
            password="secret",
            is_staff=True,
        )
        operations_group, _ = Group.objects.get_or_create(name="Operations Team")
        self.user.groups.add(operations_group)

    def test_retrieve_context_filters_access_and_expands_neighbors(self):
        source = AIKnowledgeSource.objects.create(
            source_type=AIKnowledgeSource.SOURCE_PROCEDURE,
            source_id="1",
            title="Quy trinh A",
            locale="vi",
            status=AIKnowledgeSource.STATUS_INDEXED,
            access_level=AIKnowledgeSource.ACCESS_INTERNAL,
            metadata={},
        )
        AIKnowledgeChunk.objects.create(
            source_record=source,
            source_type=source.source_type,
            source_id=source.source_id,
            section_key="default",
            chunk_index=0,
            title=source.title,
            section_title=source.title,
            content="Thong tin mo dau.",
            embedding=_vector((0, 1.0), (1, 0.0)),
            embedding_model="test",
            embedding_dim=768,
            token_count=3,
            next_chunk_index=1,
            access_level=AIKnowledgeSource.ACCESS_INTERNAL,
            locale="vi",
            status=AIKnowledgeSource.STATUS_INDEXED,
            metadata={},
        )
        AIKnowledgeChunk.objects.create(
            source_record=source,
            source_type=source.source_type,
            source_id=source.source_id,
            section_key="default",
            chunk_index=1,
            title=source.title,
            section_title=source.title,
            content="Quy trinh tiep nhan khach hang doanh nghiep.",
            embedding=_vector((0, 1.0), (1, 1.0)),
            embedding_model="test",
            embedding_dim=768,
            token_count=6,
            prev_chunk_index=0,
            next_chunk_index=2,
            access_level=AIKnowledgeSource.ACCESS_INTERNAL,
            locale="vi",
            status=AIKnowledgeSource.STATUS_INDEXED,
            metadata={},
        )
        AIKnowledgeChunk.objects.create(
            source_record=source,
            source_type=source.source_type,
            source_id=source.source_id,
            section_key="default",
            chunk_index=2,
            title=source.title,
            section_title=source.title,
            content="Thong tin ket thuc.",
            embedding=_vector((0, 1.0), (1, 0.2)),
            embedding_model="test",
            embedding_dim=768,
            token_count=3,
            prev_chunk_index=1,
            access_level=AIKnowledgeSource.ACCESS_INTERNAL,
            locale="vi",
            status=AIKnowledgeSource.STATUS_INDEXED,
            metadata={},
        )

        restricted_source = AIKnowledgeSource.objects.create(
            source_type=AIKnowledgeSource.SOURCE_CLINICAL_NOTE,
            source_id="99",
            title="Clinical",
            locale="vi",
            status=AIKnowledgeSource.STATUS_INDEXED,
            access_level=AIKnowledgeSource.ACCESS_CLINICAL,
            metadata={"patient_id": "BN-1"},
        )
        AIKnowledgeChunk.objects.create(
            source_record=restricted_source,
            source_type=restricted_source.source_type,
            source_id=restricted_source.source_id,
            section_key="default",
            chunk_index=0,
            title=restricted_source.title,
            section_title=restricted_source.title,
            content="Du lieu lam sang nhay cam.",
            embedding=_vector((0, 0.2), (1, 1.0)),
            embedding_model="test",
            embedding_dim=768,
            token_count=4,
            access_level=AIKnowledgeSource.ACCESS_CLINICAL,
            locale="vi",
            status=AIKnowledgeSource.STATUS_INDEXED,
            metadata={"patient_id": "BN-1"},
        )

        context = retrieve_context_for_question(
            user=self.user,
            question="quy trinh tiep nhan",
            query_embedding=_vector((0, 1.0), (1, 1.0)),
            source_types=[AIKnowledgeSource.SOURCE_PROCEDURE, AIKnowledgeSource.SOURCE_CLINICAL_NOTE],
            top_k=1,
        )

        self.assertTrue(any(item["chunk_index"] == 1 for item in context))
        self.assertTrue(any(item["chunk_index"] == 0 for item in context))
        self.assertTrue(any(item["chunk_index"] == 2 for item in context))
        self.assertFalse(any(item["source_type"] == AIKnowledgeSource.SOURCE_CLINICAL_NOTE for item in context))
