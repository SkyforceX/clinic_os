import json
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def get_ollama_base_url():
    return getattr(settings, "OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")


def get_ollama_model():
    return getattr(settings, "OLLAMA_MODEL", "qwen2.5:3b")


def get_ollama_system_prompt():
    return getattr(
        settings,
        "OLLAMA_SYSTEM_PROMPT",
        (
            "Bạn là trợ lý nội bộ của phòng khám doanh nghiệp ClinicOS. "
            "Nhiệm vụ của bạn là hỗ trợ đội ngũ quản lý về nghiệp vụ khám sức khỏe doanh nghiệp, "
            "hợp đồng, báo giá, lên lịch, và các vấn đề vận hành. "
            "Luôn trả lời bằng tiếng Việt, ngắn gọn và chính xác."
        ),
    )


def get_ollama_timeout():
    return int(getattr(settings, "OLLAMA_TIMEOUT", 120))


def build_messages_payload(conversation_messages):
    """
    Chuyển danh sách Message objects thành messages cho Ollama /api/chat.
    Tự động thêm system prompt ở đầu.
    """
    payload = [{"role": "system", "content": get_ollama_system_prompt()}]

    for msg in conversation_messages:
        if msg.role in ("user", "assistant"):
            payload.append(
                {
                    "role": msg.role,
                    "content": msg.content,
                }
            )

    return payload


def stream_completion(messages_payload):
    """
    Stream phản hồi từ Ollama native API /api/chat.
    Yield từng đoạn text nhỏ.
    """
    base_url = get_ollama_base_url()
    url = f"{base_url}/api/chat"
    payload = {
        "model": get_ollama_model(),
        "messages": messages_payload,
        "stream": True,
        "options": {
            "temperature": 0.7,
        },
    }

    try:
        with requests.post(
            url,
            json=payload,
            stream=True,
            timeout=get_ollama_timeout(),
        ) as response:
            response.raise_for_status()

            for raw_line in response.iter_lines(decode_unicode=True):
                if not raw_line:
                    continue

                try:
                    chunk = json.loads(raw_line)
                except json.JSONDecodeError:
                    logger.warning("Không parse được chunk từ Ollama: %s", raw_line)
                    continue

                if chunk.get("done") is True:
                    break

                message = chunk.get("message") or {}
                content = message.get("content", "")
                if content:
                    yield content

    except requests.exceptions.ConnectionError as exc:
        logger.error("Không thể kết nối Ollama tại %s: %s", url, exc)
        raise RuntimeError(
            f"Không thể kết nối đến máy chủ AI ({base_url}). "
            "Vui lòng kiểm tra Ollama đang chạy."
        ) from exc
    except requests.exceptions.Timeout as exc:
        logger.error("Ollama timeout sau %ss", get_ollama_timeout())
        raise RuntimeError("Máy chủ AI phản hồi quá lâu. Vui lòng thử lại.") from exc
    except requests.exceptions.HTTPError as exc:
        logger.error("Ollama HTTP error: %s", exc)
        try:
            detail = response.text
        except Exception:
            detail = str(exc)
        raise RuntimeError(f"Lỗi máy chủ AI: {detail}") from exc


def complete_sync(messages_payload):
    """
    Gọi Ollama /api/chat không stream, trả về toàn bộ nội dung phản hồi.
    Dùng cho auto title hoặc tác vụ cần text đầy đủ.
    """
    base_url = get_ollama_base_url()
    url = f"{base_url}/api/chat"
    payload = {
        "model": get_ollama_model(),
        "messages": messages_payload,
        "stream": False,
        "options": {
            "temperature": 0.5,
            "num_predict": 60,
        },
    }

    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        return (data.get("message") or {}).get("content", "").strip()
    except Exception as exc:
        logger.warning("Auto-title generation thất bại: %s", exc)
        return ""


def auto_generate_title(first_user_message: str) -> str:
    """
    Tự động tạo tiêu đề ngắn cho cuộc hội thoại dựa trên tin nhắn đầu tiên.
    """
    messages = [
        {
            "role": "system",
            "content": (
                "Tóm tắt nội dung câu hỏi sau thành một tiêu đề ngắn tối đa 8 từ. "
                "Chỉ trả về tiêu đề, không giải thích, không có dấu ngoặc kép."
            ),
        },
        {"role": "user", "content": first_user_message},
    ]
    title = complete_sync(messages)
    return title[:200] if title else ""