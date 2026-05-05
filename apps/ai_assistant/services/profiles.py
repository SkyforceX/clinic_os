from __future__ import annotations

from apps.ai_assistant.models import Conversation
from apps.ai_knowledge.models import AIKnowledgeSource


ASSISTANT_PROFILE_CONFIG = {
    Conversation.PROFILE_CUSTOMER: {
        "label": "Customer Bot",
        "page_title": "Tư vấn khách hàng",
        "allowed_source_types": [
            AIKnowledgeSource.SOURCE_SERVICE,
            AIKnowledgeSource.SOURCE_FAQ,
            AIKnowledgeSource.SOURCE_CATEGORY,
            AIKnowledgeSource.SOURCE_PACKAGE,
        ],
        "is_public": True,
        "system_hint": (
            "Bạn là chatbot tư vấn khách hàng. Chỉ được trả lời bằng dữ liệu công khai "
            "về dịch vụ, gói khám, FAQ và lịch công khai. Không tiết lộ dữ liệu nội bộ, "
            "hợp đồng, bệnh nhân, lâm sàng hoặc thông tin quản trị. "
            "Giọng điệu cần thân thiện, tích cực, dễ hiểu và chuyên nghiệp."
        ),
    },
    Conversation.PROFILE_STAFF: {
        "label": "Staff Bot",
        "page_title": "Trợ lý nội bộ",
        "allowed_source_types": [
            AIKnowledgeSource.SOURCE_SERVICE,
            AIKnowledgeSource.SOURCE_FAQ,
            AIKnowledgeSource.SOURCE_CATEGORY,
            AIKnowledgeSource.SOURCE_PACKAGE,
            AIKnowledgeSource.SOURCE_PROCEDURE,
            AIKnowledgeSource.SOURCE_INTERNAL_NOTE,
            AIKnowledgeSource.SOURCE_POLICY,
            AIKnowledgeSource.SOURCE_DOCUMENT,
            AIKnowledgeSource.SOURCE_CONTRACT,
            AIKnowledgeSource.SOURCE_QUOTATION,
            AIKnowledgeSource.SOURCE_VISIT_SUMMARY,
            AIKnowledgeSource.SOURCE_CLINICAL_NOTE,
            AIKnowledgeSource.SOURCE_MEDICAL_RECORD,
            AIKnowledgeSource.SOURCE_PATIENT_SUMMARY,
        ],
        "is_public": False,
        "system_hint": (
            "Bạn là trợ lý nội bộ cho nhân viên Clinic OS. Ưu tiên trả lời ngắn gọn, đúng quy trình "
            "và đúng phân quyền. Nếu thông tin nằm ngoài quyền của người dùng, phải từ chối hoặc "
            "chỉ trả về dữ liệu an toàn. Giọng điệu cần tích cực, chủ động hỗ trợ và chuyên nghiệp."
        ),
    },
    Conversation.PROFILE_MANAGER: {
        "label": "Manager Bot",
        "page_title": "Trợ lý cấp quản lý",
        "allowed_source_types": [
            AIKnowledgeSource.SOURCE_SERVICE,
            AIKnowledgeSource.SOURCE_FAQ,
            AIKnowledgeSource.SOURCE_CATEGORY,
            AIKnowledgeSource.SOURCE_PACKAGE,
            AIKnowledgeSource.SOURCE_PROCEDURE,
            AIKnowledgeSource.SOURCE_INTERNAL_NOTE,
            AIKnowledgeSource.SOURCE_POLICY,
            AIKnowledgeSource.SOURCE_DOCUMENT,
            AIKnowledgeSource.SOURCE_CONTRACT,
            AIKnowledgeSource.SOURCE_QUOTATION,
            AIKnowledgeSource.SOURCE_VISIT_SUMMARY,
            AIKnowledgeSource.SOURCE_CLINICAL_NOTE,
            AIKnowledgeSource.SOURCE_MEDICAL_RECORD,
            AIKnowledgeSource.SOURCE_PATIENT_SUMMARY,
        ],
        "is_public": False,
        "system_hint": (
            "Bạn là trợ lý cấp quản lý. Được phép tổng hợp vận hành, hợp đồng, báo giá, quy trình "
            "và các thông tin nội bộ theo đúng quyền của người dùng. Ưu tiên số liệu thực tế khi có "
            "tool hoặc truy vấn runtime. Giọng điệu cần súc tích, rõ nghĩa, chuyên nghiệp và định hướng hành động."
        ),
    },
}


def get_assistant_profile_config(profile: str) -> dict:
    return ASSISTANT_PROFILE_CONFIG.get(
        profile,
        ASSISTANT_PROFILE_CONFIG[Conversation.PROFILE_MANAGER],
    )
