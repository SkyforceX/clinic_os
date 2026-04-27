import json
import logging
import re
import unicodedata
from urllib.parse import urlparse

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

MODEL_DISCLOSURE_RESPONSE = (
    "Ôi là mô hình ngôn ngữ Qwen được phát triển bởi Alibaba Cloud. "
    "Dữ liệu huấn luyện của tôi bao gồm nhiều nguồn thông tin đa dạng, nhưng không có quyền truy cập dữ liệu thời gian thực "
    "hoặc cơ sở dữ liệu nội bộ của ClinicOS. Nếu bạn có câu hỏi cụ thể về dịch vụ, báo giá, hoặc quy trình của ClinicOS, "
    "vui lòng cung cấp thêm thông tin để tôi hỗ trợ chính xác hơn."
)

SYSTEM_SECURITY_RESPONSE = (
    "Tôi không thể cung cấp thông tin về kiến trúc hệ thống, công nghệ, cấu hình triển khai, "
    "hoặc cơ chế bảo mật nội bộ của ClinicOS. Tôi chỉ hỗ trợ các nội dung được phép như tổ chức, "
    "nghiệp vụ, quy trình, dịch vụ và dữ liệu đã được chia sẻ hợp lệ."
)

MODEL_DISCLOSURE_PATTERNS = (
    "model gi",
    "mo hinh gi",
    "ban la model gi",
    "ban la mo hinh gi",
    "nguon nao",
    "nguon du lieu",
    "du lieu huan luyen",
    "duoc huan luyen tu dau",
    "ban duoc train",
    "ban duoc huan luyen",
    "qwen",
    "alibaba cloud",
)

SECURITY_DISCLOSURE_PATTERNS = (
    "kien truc he thong",
    "kien truc cua he thong",
    "cong nghe nen tang",
    "tech stack",
    "stack cong nghe",
    "he thong chay tren",
    "co so du lieu noi bo",
    "database noi bo",
    "cau hinh trien khai",
    "ha tang",
    "bao mat noi bo",
    "system prompt",
    "prompt he thong",
)


def _normalize_text(value):
    normalized = unicodedata.normalize("NFKD", (value or "").strip().lower())
    without_accents = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    return re.sub(r"\s+", " ", without_accents)


def _is_loopback_url(url):
    hostname = urlparse((url or "").strip()).hostname
    return hostname in {"127.0.0.1", "localhost", "::1"}


def get_ollama_base_url():
    ollama_url = getattr(settings, "OLLAMA_BASE_URL", "").strip()
    ai_url = getattr(settings, "AI_BASE_URL", "").strip()

    candidates = [url for url in (ollama_url, ai_url) if url]
    if not candidates:
        return "http://127.0.0.1:11434"

    non_loopback_candidates = [url for url in candidates if not _is_loopback_url(url)]
    selected_url = (
        non_loopback_candidates[0] if non_loopback_candidates else candidates[0]
    )
    return selected_url.rstrip("/")


def get_ollama_model():
    return getattr(settings, "OLLAMA_MODEL", "qwen2.5:3b")


def get_ollama_system_prompt():
    prompt = getattr(settings, "AI_SYSTEM_PROMPT", "").strip()
    if prompt:
        return prompt
    return getattr(settings, "OLLAMA_SYSTEM_PROMPT", "").strip()


def get_guardrail_response(user_content: str):
    normalized = _normalize_text(user_content)

    if any(pattern in normalized for pattern in MODEL_DISCLOSURE_PATTERNS):
        return MODEL_DISCLOSURE_RESPONSE

    if any(pattern in normalized for pattern in SECURITY_DISCLOSURE_PATTERNS):
        return SYSTEM_SECURITY_RESPONSE

    return ""


def get_ollama_timeout():
    return int(getattr(settings, "OLLAMA_TIMEOUT", 120))


def build_messages_payload(conversation_messages, knowledge_context: str = ""):
    """
    Chuyển danh sách Message objects thành messages cho Ollama /api/chat.
    Tự động thêm system prompt ở đầu.
    """
    payload = [{"role": "system", "content": get_ollama_system_prompt()}]

    if knowledge_context:
        payload.append(
            {
                "role": "system",
                "content": (
                    "Bối cảnh tri thức nội bộ bổ sung:\n"
                    f"{knowledge_context}\n\n"
                    "Ưu tiên sử dụng bối cảnh này khi phù hợp. "
                    "Không khẳng định những gì không có trong dữ liệu."
                ),
            }
        )

    for msg in conversation_messages:
        if msg.role in ("user", "assistant"):
            payload.append(
                {
                    "role": msg.role,
                    "content": msg.content,
                }
            )

    return payload


def _build_generate_prompt(messages_payload):
    prompt_parts = []
    for message in messages_payload:
        role = message.get("role")
        content = (message.get("content") or "").strip()
        if not content:
            continue
        if role == "system":
            prompt_parts.append(f"[HỆ THỐNG]\n{content}")
        elif role == "user":
            prompt_parts.append(f"[NGƯỜI DÙNG]\n{content}")
        elif role == "assistant":
            prompt_parts.append(f"[TRỢ LÝ]\n{content}")

    prompt_parts.append("[TRỢ LÝ]\n")
    return "\n\n".join(prompt_parts)


def _iter_chat_stream(response):
    for raw_line in response.iter_lines(decode_unicode=True):
        if not raw_line:
            continue

        try:
            chunk = json.loads(raw_line)
        except json.JSONDecodeError:
            logger.warning("Không parse được chunk từ Ollama chat: %s", raw_line)
            continue

        if chunk.get("done") is True:
            break

        message = chunk.get("message") or {}
        content = message.get("content", "")
        if content:
            yield content
            continue

        # Qwen3/Ollama có thể stream pha "thinking" trước khi có content thực.
        # Yield một khoảng trắng để giữ kết nối SSE sống, tránh upstream/proxy 504.
        thinking = message.get("thinking", "")
        if thinking:
            yield " "


def _iter_generate_stream(response):
    for raw_line in response.iter_lines(decode_unicode=True):
        if not raw_line:
            continue

        try:
            chunk = json.loads(raw_line)
        except json.JSONDecodeError:
            logger.warning("Không parse được chunk từ Ollama generate: %s", raw_line)
            continue

        if chunk.get("done") is True:
            break

        content = chunk.get("response", "")
        if content:
            yield content


def _iter_openai_chat_stream(response):
    for raw_line in response.iter_lines(decode_unicode=True):
        if not raw_line:
            continue

        line = raw_line.strip()
        if not line.startswith("data:"):
            continue

        data_part = line[5:].strip()
        if data_part == "[DONE]":
            break

        try:
            chunk = json.loads(data_part)
        except json.JSONDecodeError:
            logger.warning(
                "Khong parse duoc chunk tu OpenAI-compatible chat: %s", raw_line
            )
            continue

        for choice in chunk.get("choices", []):
            delta = choice.get("delta") or {}
            content = delta.get("content", "")
            if content:
                yield content


def _raise_user_facing_runtime_error(exc, url):
    if isinstance(exc, requests.exceptions.ConnectionError):
        logger.error("Không thể kết nối Ollama tại %s: %s", url, exc)
        raise RuntimeError(
            "Không thể kết nối đến máy chủ AI. "
            "Vui lòng liên hệ quản trị viên hệ thống."
        ) from exc
    if isinstance(exc, requests.exceptions.Timeout):
        logger.error("Ollama timeout sau %ss", get_ollama_timeout())
        raise RuntimeError("Máy chủ AI phản hồi quá lâu. Vui lòng thử lại.") from exc
    if isinstance(exc, requests.exceptions.HTTPError):
        logger.error("Ollama HTTP error: %s", exc)
        raise RuntimeError(
            "Máy chủ AI tạm thời không khả dụng. Vui lòng thử lại sau."
        ) from exc
    raise exc


def _stream_openai_chat_completion(base_url, messages_payload):
    openai_url = f"{base_url}/v1/chat/completions"
    openai_payload = {
        "model": get_ollama_model(),
        "messages": messages_payload,
        "stream": True,
        "temperature": 0.7,
    }
    logger.warning("Fallback sang OpenAI-compatible /v1/chat/completions")

    try:
        with requests.post(
            openai_url,
            json=openai_payload,
            stream=True,
            timeout=get_ollama_timeout(),
        ) as response:
            response.raise_for_status()
            yield from _iter_openai_chat_stream(response)
    except Exception as exc:
        _raise_user_facing_runtime_error(exc, openai_url)


def _complete_openai_chat_sync(base_url, messages_payload):
    openai_url = f"{base_url}/v1/chat/completions"
    openai_payload = {
        "model": get_ollama_model(),
        "messages": messages_payload,
        "stream": False,
        "temperature": 0.5,
        "max_tokens": 60,
    }
    logger.warning("Fallback sync sang OpenAI-compatible /v1/chat/completions")

    try:
        response = requests.post(openai_url, json=openai_payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            return ""
        message = choices[0].get("message") or {}
        return (message.get("content") or "").strip()
    except Exception as exc:
        logger.warning("OpenAI-compatible sync that bai: %s", exc)
        return ""


def stream_completion(messages_payload):
    """
    Stream phản hồi từ Ollama.
    Ưu tiên /api/chat, fallback sang /api/generate nếu local Ollama cũ chưa hỗ trợ.
    """
    base_url = get_ollama_base_url()
    chat_url = f"{base_url}/api/chat"
    chat_payload = {
        "model": get_ollama_model(),
        "messages": messages_payload,
        "stream": True,
        "options": {
            "temperature": 0.7,
        },
    }

    try:
        with requests.post(
            chat_url,
            json=chat_payload,
            stream=True,
            timeout=get_ollama_timeout(),
        ) as response:
            response.raise_for_status()
            yield from _iter_chat_stream(response)
            return
    except requests.exceptions.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        if status_code != 404:
            _raise_user_facing_runtime_error(exc, chat_url)
    except Exception as exc:
        _raise_user_facing_runtime_error(exc, chat_url)

    generate_url = f"{base_url}/api/generate"
    generate_payload = {
        "model": get_ollama_model(),
        "prompt": _build_generate_prompt(messages_payload),
        "stream": True,
        "options": {
            "temperature": 0.7,
        },
    }
    logger.warning("Ollama /api/chat không hỗ trợ, fallback sang /api/generate")

    try:
        with requests.post(
            generate_url,
            json=generate_payload,
            stream=True,
            timeout=get_ollama_timeout(),
        ) as response:
            response.raise_for_status()
            yield from _iter_generate_stream(response)
    except Exception as exc:
        if isinstance(exc, requests.exceptions.HTTPError):
            status_code = exc.response.status_code if exc.response is not None else None
            if status_code == 404:
                yield from _stream_openai_chat_completion(base_url, messages_payload)
                return
        _raise_user_facing_runtime_error(exc, generate_url)


def complete_sync(messages_payload):
    """
    Gọi Ollama không stream, trả về toàn bộ nội dung phản hồi.
    Dùng cho auto title hoặc tác vụ cần text đầy đủ.
    """
    base_url = get_ollama_base_url()
    chat_url = f"{base_url}/api/chat"
    chat_payload = {
        "model": get_ollama_model(),
        "messages": messages_payload,
        "stream": False,
        "options": {
            "temperature": 0.5,
            "num_predict": 60,
        },
    }

    try:
        response = requests.post(chat_url, json=chat_payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        return (data.get("message") or {}).get("content", "").strip()
    except requests.exceptions.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        if status_code != 404:
            logger.warning("Auto-title generation HTTP error: %s", exc)
            return ""
    except Exception as exc:
        logger.warning("Auto-title generation thất bại: %s", exc)
        return ""

    generate_url = f"{base_url}/api/generate"
    generate_payload = {
        "model": get_ollama_model(),
        "prompt": _build_generate_prompt(messages_payload),
        "stream": False,
        "options": {
            "temperature": 0.5,
            "num_predict": 60,
        },
    }
    logger.warning("Ollama /api/chat không hỗ trợ sync, fallback sang /api/generate")

    try:
        response = requests.post(generate_url, json=generate_payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        return (data.get("response") or "").strip()
    except Exception as exc:
        if isinstance(exc, requests.exceptions.HTTPError):
            status_code = exc.response.status_code if exc.response is not None else None
            if status_code == 404:
                return _complete_openai_chat_sync(base_url, messages_payload)
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
