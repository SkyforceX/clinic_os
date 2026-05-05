from __future__ import annotations

import re
import unicodedata

from apps.ai_assistant.models import Message


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", (value or "").strip().lower())
    without_accents = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    return re.sub(r"\s+", " ", without_accents)


def _detect_preference(messages) -> str:
    combined_text = " ".join((message.content or "") for message in messages if message.role == Message.ROLE_USER)
    normalized = _normalize_text(combined_text)
    preferences: list[str] = []
    if "tieng viet co dau" in normalized or "viet co dau" in normalized:
        preferences.append("Người dùng muốn câu trả lời bằng tiếng Việt có dấu đầy đủ.")
    if "ngan gon" in normalized or "tom tat" in normalized:
        preferences.append("Người dùng thiên về câu trả lời ngắn gọn, súc tích.")
    if "chi tiet" in normalized or "giai thich ky" in normalized:
        preferences.append("Người dùng có thể muốn giải thích chi tiết hơn khi cần.")
    return " ".join(preferences)


def build_conversation_state(messages) -> str:
    recent_messages = list(messages)[-6:]
    if not recent_messages:
        return ""

    recent_user_messages = [
        (message.content or "").strip()
        for message in recent_messages
        if message.role == Message.ROLE_USER and (message.content or "").strip()
    ]
    recent_assistant_messages = [
        (message.content or "").strip()
        for message in recent_messages
        if message.role == Message.ROLE_ASSISTANT and (message.content or "").strip()
    ]

    parts: list[str] = []
    if recent_user_messages:
        parts.append(f"Yêu cầu gần đây của người dùng: {recent_user_messages[-1]}")
    if len(recent_user_messages) >= 2:
        parts.append(f"Ngữ cảnh trước đó của người dùng: {recent_user_messages[-2]}")
    if recent_assistant_messages:
        parts.append(f"Phản hồi gần nhất của trợ lý: {recent_assistant_messages[-1]}")

    preference_hint = _detect_preference(recent_messages)
    if preference_hint:
        parts.append(preference_hint)

    parts.append(
        "Giữ liên tục chủ đề hội thoại. Nếu người dùng dùng các từ như 'cái này', 'ý đó', 'trường hợp trên', "
        "hãy ưu tiên nối với ngữ cảnh gần nhất thay vì trả lời như một câu hỏi hoàn toàn mới."
    )
    return "\n".join(parts)
