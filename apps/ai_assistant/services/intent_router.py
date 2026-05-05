from __future__ import annotations

import re
import unicodedata

from apps.ai_assistant.models import Conversation

from .profiles import get_assistant_profile_config
from .tool_router import route_tool_call


GREETING_PATTERNS = ("xin chao", "chao", "hello", "hi", "alo")
THANKS_PATTERNS = ("cam on", "thank you", "thanks")
CAPABILITY_PATTERNS = (
    "ban lam duoc gi",
    "ban co the lam gi",
    "ho tro gi",
    "giup duoc gi",
)
STYLE_DIRECTIVE_PATTERNS = (
    "tra loi bang tieng viet co dau",
    "tra loi bang tieng viet",
    "viet bang tieng viet co dau",
    "viet co dau",
    "ngan gon hon",
    "lich su hon",
    "chuyen nghiep hon",
)
AMBIGUOUS_PATTERNS = (
    "cai nay",
    "cai kia",
    "van de nay",
    "van de do",
    "y nay",
    "y do",
    "truong hop tren",
    "nhu vay la sao",
    "y la sao",
)


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", (value or "").strip().lower())
    without_accents = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    return re.sub(r"\s+", " ", without_accents)


def _build_capability_response(profile: str) -> str:
    label = get_assistant_profile_config(profile).get("label", "Trợ lý AI")
    if profile == Conversation.PROFILE_CUSTOMER:
        return (
            f"Tôi là {label}. Tôi có thể hỗ trợ tư vấn dịch vụ, gói khám, FAQ công khai "
            "và một số thông tin lịch công khai. Nếu bạn muốn, hãy nói rõ nhu cầu như tìm gói khám, "
            "hỏi dịch vụ hoặc cần hướng dẫn đặt lịch."
        )
    if profile == Conversation.PROFILE_STAFF:
        return (
            f"Tôi là {label}. Tôi có thể hỗ trợ tra cứu quy trình, chính sách, dịch vụ, "
            "thông tin nội bộ trong phạm vi được phép, và trả lời một số câu hỏi thống kê cơ bản. "
            "Bạn cứ nêu rõ nghiệp vụ hoặc dữ liệu cần tra cứu."
        )
    return (
        f"Tôi là {label}. Tôi có thể hỗ trợ tổng hợp thông tin vận hành, báo giá, hợp đồng, "
        "quy trình và một số câu hỏi thống kê trong phạm vi quyền truy cập. "
        "Bạn có thể hỏi theo chủ đề, thời gian, công ty hoặc trạng thái cụ thể."
    )


def _build_social_response(normalized: str, profile: str) -> str:
    if any(pattern == normalized for pattern in GREETING_PATTERNS):
        if profile == Conversation.PROFILE_CUSTOMER:
            return "Xin chào. Tôi sẵn sàng hỗ trợ bạn về dịch vụ, gói khám và các thông tin công khai."
        return "Xin chào. Tôi sẵn sàng hỗ trợ bạn. Bạn cần tra cứu hoặc xử lý nội dung gì?"
    if any(pattern in normalized for pattern in THANKS_PATTERNS):
        return "Rất sẵn lòng. Nếu cần, bạn cứ hỏi tiếp, tôi sẽ hỗ trợ đến cùng."
    return ""


def _build_style_response(normalized: str) -> str:
    if "tieng viet" in normalized or "co dau" in normalized:
        return (
            "Được. Từ bây giờ tôi sẽ trả lời bằng tiếng Việt có dấu đầy đủ, rõ ràng và tự nhiên."
        )
    if "ngan gon hon" in normalized:
        return "Được. Từ bây giờ tôi sẽ ưu tiên trả lời ngắn gọn và đi thẳng vào ý chính."
    if "lich su hon" in normalized:
        return "Được. Từ bây giờ tôi sẽ giữ giọng điệu lịch sự và mềm mại hơn."
    if "chuyen nghiep hon" in normalized:
        return "Được. Từ bây giờ tôi sẽ giữ cách trả lời chuyên nghiệp và súc tích hơn."
    return ""


def _build_ambiguity_response(normalized: str, has_history: bool) -> str:
    if normalized in {"sao", "roi sao", "the nao", "giai thich them", "noi ro hon"}:
        return "Bạn muốn tôi làm rõ phần nào cụ thể hơn? Bạn có thể nhắc lại chủ đề hoặc nội dung đang nói tới."
    if len(normalized.split()) <= 3:
        if has_history:
            return "Bạn đang muốn nói tiếp ý nào trong phần trước? Bạn có thể nhắc ngắn gọn chủ đề để tôi theo đúng mạch."
        return "Bạn có thể nói rõ hơn nội dung cần hỏi được không? Tôi muốn hiểu đúng ý trước khi trả lời."
    if any(pattern in normalized for pattern in AMBIGUOUS_PATTERNS):
        return "Câu hỏi của bạn chưa đủ rõ để tôi trả lời chính xác. Bạn có thể nói rõ đối tượng hoặc nội dung bạn đang nhắc tới không?"
    return ""


def route_pre_llm_action(*, conversation, user, question: str, profile: str) -> str | None:
    normalized = _normalize_text(question)
    if not normalized:
        return "Bạn muốn tôi hỗ trợ nội dung nào cụ thể hơn?"

    social_response = _build_social_response(normalized, profile)
    if social_response:
        return social_response

    if any(pattern in normalized for pattern in CAPABILITY_PATTERNS):
        return _build_capability_response(profile)

    if any(pattern in normalized for pattern in STYLE_DIRECTIVE_PATTERNS):
        return _build_style_response(normalized)

    has_history = conversation.messages.exclude(role="system").count() > 1
    ambiguity_response = _build_ambiguity_response(normalized, has_history)
    if ambiguity_response:
        return ambiguity_response

    tool_response = route_tool_call(
        user=user,
        question=question,
        profile=profile,
    )
    if tool_response:
        return tool_response

    return None
