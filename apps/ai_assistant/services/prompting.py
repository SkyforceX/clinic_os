from __future__ import annotations

import re
import unicodedata

from .llm_client import get_ollama_system_prompt
from .profiles import get_assistant_profile_config
from .response_policy import build_response_policy


MODEL_DISCLOSURE_RESPONSE = (
    "Tôi là mô hình ngôn ngữ Qwen được phát triển bởi Alibaba Cloud. "
    "Tôi không có quyền truy cập dữ liệu thời gian thực hoặc cơ sở dữ liệu nội bộ của ClinicOS. "
    "Nếu bạn cần thông tin nghiệp vụ ClinicOS, vui lòng đặt câu hỏi cụ thể hơn."
)

SYSTEM_SECURITY_RESPONSE = (
    "Tôi không thể cung cấp thông tin về kiến trúc hệ thống, công nghệ, cấu hình triển khai "
    "hoặc cơ chế bảo mật nội bộ của ClinicOS. Tôi chỉ hỗ trợ nội dung nghiệp vụ được phép."
)

MODEL_DISCLOSURE_PATTERNS = (
    "model gi",
    "mo hinh gi",
    "ban la model gi",
    "ban la mo hinh gi",
    "nguon nao",
    "nguon du lieu",
    "du lieu huan luyen",
    "qwen",
    "alibaba cloud",
)

SECURITY_DISCLOSURE_PATTERNS = (
    "kien truc he thong",
    "tech stack",
    "stack cong nghe",
    "co so du lieu noi bo",
    "database noi bo",
    "cau hinh trien khai",
    "bao mat noi bo",
    "system prompt",
    "prompt he thong",
)


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", (value or "").strip().lower())
    without_accents = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    return re.sub(r"\s+", " ", without_accents)


def get_guardrail_response(user_content: str) -> str:
    normalized = _normalize_text(user_content)
    if any(pattern in normalized for pattern in MODEL_DISCLOSURE_PATTERNS):
        return MODEL_DISCLOSURE_RESPONSE
    if any(pattern in normalized for pattern in SECURITY_DISCLOSURE_PATTERNS):
        return SYSTEM_SECURITY_RESPONSE
    return ""


def format_context_chunks(context_chunks: list[dict]) -> str:
    if not context_chunks:
        return ""
    parts = [
        "Dưới đây là ngữ cảnh nội bộ đã được phép truy cập. Chỉ sử dụng nếu thực sự phù hợp với câu hỏi.",
        "Nếu ngữ cảnh chưa đủ thông tin, hãy nói rõ là chưa đủ dữ liệu thay vì tự suy đoán.",
    ]
    for index, item in enumerate(context_chunks, start=1):
        parts.append(
            "\n".join(
                [
                    f"[Nguồn {index}] {item.get('title') or item.get('section_title') or item.get('source_type')}",
                    f"Loại: {item.get('source_type')}",
                    f"Độ liên quan: {float(item.get('similarity') or 0):.3f}",
                    item.get("content", "").strip(),
                ]
            ).strip()
        )
    return "\n\n".join(part for part in parts if part)


def build_messages_payload(
    conversation_messages,
    knowledge_context: str = "",
    profile: str = "manager",
    conversation_state: str = "",
):
    payload = [{"role": "system", "content": get_ollama_system_prompt()}]
    payload.append(
        {
            "role": "system",
            "content": (
                "Luôn trả lời bằng tiếng Việt có dấu đầy đủ, tự nhiên, rõ ràng và chuyên nghiệp, "
                "trừ khi người dùng chủ động yêu cầu một ngôn ngữ khác. "
                "Tuyệt đối không sử dụng tiếng Trung (Chinese/Mandarin), tiếng Anh hoặc bất kỳ ngôn ngữ nào khác ngoài tiếng Việt. "
                "Không chuyển sang tiếng Việt không dấu chỉ vì câu hỏi hoặc ngữ cảnh không có dấu. "
                "Nếu câu hỏi chưa rõ chủ thể, phạm vi hoặc mục tiêu, hãy hỏi lại đúng một câu ngắn gọn để làm rõ trước khi trả lời. "
                "Không bịa ý người dùng và không trả lời sang một chủ đề khác không liên quan."
            ),
        }
    )
    payload.append({"role": "system", "content": build_response_policy(profile)})

    profile_hint = get_assistant_profile_config(profile).get("system_hint", "").strip()
    if profile_hint:
        payload.append({"role": "system", "content": profile_hint})

    if conversation_state:
        payload.append(
            {
                "role": "system",
                "content": (
                    "Đây là trạng thái hội thoại gần nhất để bạn giữ đúng mạch trao đổi:\n"
                    f"{conversation_state}"
                ),
            }
        )

    if knowledge_context:
        payload.append(
            {
                "role": "system",
                "content": (
                    "Bạn phải ưu tiên ngữ cảnh nội bộ được cấp sau đây khi nó phù hợp.\n"
                    f"{knowledge_context}\n\n"
                    "Chỉ sử dụng thông tin từ ngữ cảnh nếu trực tiếp trả lời câu hỏi của người dùng. "
                    "Không đề cập, không liệt kê các dịch vụ hoặc gói khám mà người dùng không hỏi tới. "
                    "Không được khẳng định những gì không có trong ngữ cảnh."
                ),
            }
        )
    for message in conversation_messages:
        if message.role in {"user", "assistant"}:
            payload.append({"role": message.role, "content": message.content})
    return payload
