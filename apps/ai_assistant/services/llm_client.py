from __future__ import annotations

import json
import logging
from urllib.parse import urlparse

import requests
from django.conf import settings


logger = logging.getLogger(__name__)


def _is_loopback_url(url):
    hostname = urlparse((url or "").strip()).hostname
    return hostname in {"127.0.0.1", "localhost", "::1"}


def get_ollama_base_url():
    ollama_url = getattr(settings, "OLLAMA_BASE_URL", "").strip()
    ai_url = getattr(settings, "AI_BASE_URL", "").strip()
    candidates = [url for url in (ollama_url, ai_url) if url]
    if not candidates:
        return "http://127.0.0.1:11434"
    non_loopback = [url for url in candidates if not _is_loopback_url(url)]
    return (non_loopback[0] if non_loopback else candidates[0]).rstrip("/")


def get_ai_api_key() -> str:
    return getattr(settings, "AI_API_KEY", "").strip()


def _get_auth_headers() -> dict:
    key = get_ai_api_key()
    return {"Authorization": f"Bearer {key}"} if key else {}


def _use_openai_compat_mode() -> bool:
    """True khi base URL là external API (Groq, RunPod...) hoặc có API key."""
    return bool(get_ai_api_key()) or not _is_loopback_url(get_ollama_base_url())


def _is_reasoning_model(model: str) -> bool:
    """Reasoning models (QwQ, DeepSeek-R1, o1...) không hỗ trợ tham số temperature."""
    name = (model or "").lower()
    return any(kw in name for kw in ("qwq", "deepseek-r1", "o1-", "o3-", "thinking"))


def _has_thinking_mode(model: str) -> bool:
    """Models có optional thinking mode (Qwen3) — cần tắt để tránh <think> tags lẫn tiếng Anh."""
    name = (model or "").lower()
    return "qwen3" in name


def get_ollama_model():
    if _use_openai_compat_mode():
        ai_model = getattr(settings, "AI_MODEL", "").strip()
        if ai_model:
            return ai_model
    return getattr(settings, "OLLAMA_MODEL", "qwen2.5:3b")


def get_toolcall_model():
    configured = getattr(settings, "AI_TOOLCALL_MODEL", "").strip()
    return configured or get_ollama_model()


def get_toolcall_fallback_model():
    return getattr(settings, "AI_TOOLCALL_FALLBACK_MODEL", "").strip()


def get_toolcall_candidate_models() -> list[str]:
    primary = get_toolcall_model()
    fallback = get_toolcall_fallback_model()
    models: list[str] = []
    for name in (primary, fallback):
        candidate = (name or "").strip()
        if candidate and candidate not in models:
            models.append(candidate)
    return models or [get_ollama_model()]


def get_ollama_system_prompt():
    prompt = getattr(settings, "AI_SYSTEM_PROMPT", "").strip()
    if prompt:
        return prompt
    return getattr(settings, "OLLAMA_SYSTEM_PROMPT", "").strip()


def get_ollama_timeout():
    return int(getattr(settings, "OLLAMA_TIMEOUT", 120))


def get_toolcall_timeout():
    return int(getattr(settings, "AI_TOOLCALL_TIMEOUT", 25))


def get_toolcall_final_timeout():
    return int(getattr(settings, "AI_TOOLCALL_FINAL_TIMEOUT", get_toolcall_timeout()))


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
            logger.warning("Could not parse Ollama chat chunk: %s", raw_line)
            continue
        if chunk.get("done") is True:
            break
        content = (chunk.get("message") or {}).get("content", "")
        if content:
            yield content


def _iter_generate_stream(response):
    for raw_line in response.iter_lines(decode_unicode=True):
        if not raw_line:
            continue
        try:
            chunk = json.loads(raw_line)
        except json.JSONDecodeError:
            logger.warning("Could not parse Ollama generate chunk: %s", raw_line)
            continue
        if chunk.get("done") is True:
            break
        content = chunk.get("response", "")
        if content:
            yield content


def _iter_openai_chat_stream(response):
    response.encoding = "utf-8"  # Groq trả UTF-8 nhưng Content-Type không ghi charset → requests default ISO-8859-1
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
            logger.warning("Could not parse OpenAI-compatible chunk: %s", raw_line)
            continue
        for choice in chunk.get("choices", []):
            content = (choice.get("delta") or {}).get("content", "")
            if content:
                yield content


def _raise_user_facing_runtime_error(exc, url):
    if isinstance(exc, requests.exceptions.ConnectionError):
        logger.error("Cannot connect to AI server %s: %s", url, exc)
        raise RuntimeError(
            "Không thể kết nối đến máy chủ AI. Vui lòng liên hệ quản trị viên hệ thống."
        ) from exc
    if isinstance(exc, requests.exceptions.Timeout):
        logger.error("AI timeout after %ss", get_ollama_timeout())
        raise RuntimeError("Máy chủ AI phản hồi quá lâu. Vui lòng thử lại.") from exc
    if isinstance(exc, requests.exceptions.HTTPError):
        body = ""
        if exc.response is not None:
            try:
                body = exc.response.text[:300]
            except Exception:
                pass
        logger.error("AI HTTP error: %s | response body: %s", exc, body)
        raise RuntimeError(
            "Máy chủ AI tạm thời không khả dụng. Vui lòng thử lại sau."
        ) from exc
    raise exc


def _stream_openai_chat_completion(base_url, messages_payload, *, temperature=0.7):
    model = get_ollama_model()
    payload = {
        "model": model,
        "messages": messages_payload,
        "stream": True,
    }
    if not _is_reasoning_model(model):
        payload["temperature"] = temperature
    if _has_thinking_mode(model):
        payload["reasoning_effort"] = "none"
    url = f"{base_url}/v1/chat/completions"
    with requests.post(
        url,
        json=payload,
        headers=_get_auth_headers(),
        stream=True,
        timeout=get_ollama_timeout(),
    ) as response:
        if not response.ok:
            # Đọc body trước raise_for_status vì stream=True không auto-buffer body lỗi
            body = response.content.decode("utf-8", errors="replace")[:400]
            logger.error("AI API %s | url: %s | body: %s", response.status_code, url, body)
            response.raise_for_status()
        yield from _iter_openai_chat_stream(response)


def _complete_openai_chat_sync(base_url, messages_payload, *, temperature=0.5, max_tokens=60, timeout=30):
    url = f"{base_url}/v1/chat/completions"
    model = get_ollama_model()
    payload = {
        "model": model,
        "messages": messages_payload,
        "stream": False,
        "max_tokens": max_tokens,
    }
    if not _is_reasoning_model(model):
        payload["temperature"] = temperature
    if _has_thinking_mode(model):
        payload["reasoning_effort"] = "none"
    try:
        response = requests.post(url, json=payload, headers=_get_auth_headers(), timeout=timeout)
        response.raise_for_status()
        choices = response.json().get("choices") or []
        if not choices:
            return ""
        return ((choices[0].get("message") or {}).get("content") or "").strip()
    except Exception as exc:
        logger.warning("OpenAI-compatible sync fallback failed: %s", exc)
        return ""


def complete_openai_chat_message(
    messages_payload,
    *,
    model=None,
    temperature=0.5,
    max_tokens=220,
    timeout=30,
):
    base_url = get_ollama_base_url()
    url = f"{base_url}/v1/chat/completions"
    resolved_model = model or get_ollama_model()
    payload = {
        "model": resolved_model,
        "messages": messages_payload,
        "stream": False,
        "max_tokens": max_tokens,
    }
    if not _is_reasoning_model(resolved_model):
        payload["temperature"] = temperature
    if _has_thinking_mode(resolved_model):
        payload["reasoning_effort"] = "none"
    try:
        response = requests.post(url, json=payload, headers=_get_auth_headers(), timeout=timeout)
        response.raise_for_status()
        choices = response.json().get("choices") or []
        if not choices:
            return None
        return choices[0]
    except Exception as exc:
        logger.warning("OpenAI-compatible chat request failed: %s", exc)
        return None


def complete_openai_chat_with_tools(
    messages_payload,
    *,
    tools,
    model=None,
    temperature=0.1,
    max_tokens=220,
    timeout=30,
    tool_choice="auto",
):
    base_url = get_ollama_base_url()
    url = f"{base_url}/v1/chat/completions"
    resolved_model = model or get_ollama_model()
    payload = {
        "model": resolved_model,
        "messages": messages_payload,
        "stream": False,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "tools": tools,
        "tool_choice": tool_choice,
    }
    if _has_thinking_mode(resolved_model):
        payload["reasoning_effort"] = "none"
    try:
        response = requests.post(url, json=payload, headers=_get_auth_headers(), timeout=timeout)
        response.raise_for_status()
        choices = response.json().get("choices") or []
        if not choices:
            return None
        return choices[0].get("message") or None
    except Exception as exc:
        logger.warning("OpenAI-compatible tool call request failed: %s", exc)
        return None


def stream_completion(messages_payload, *, temperature=0.7):
    base_url = get_ollama_base_url()

    # External API (Groq, RunPod...): đi thẳng vào /v1/chat/completions
    if _use_openai_compat_mode():
        try:
            yield from _stream_openai_chat_completion(base_url, messages_payload, temperature=temperature)
        except Exception as exc:
            _raise_user_facing_runtime_error(exc, f"{base_url}/v1/chat/completions")
        return

    # Ollama local: thử /api/chat → /api/generate → fallback /v1/chat/completions
    chat_url = f"{base_url}/api/chat"
    chat_payload = {
        "model": get_ollama_model(),
        "messages": messages_payload,
        "stream": True,
        "options": {"temperature": temperature},
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
        if exc.response is None or exc.response.status_code != 404:
            _raise_user_facing_runtime_error(exc, chat_url)
    except Exception as exc:
        _raise_user_facing_runtime_error(exc, chat_url)

    generate_url = f"{base_url}/api/generate"
    generate_payload = {
        "model": get_ollama_model(),
        "prompt": _build_generate_prompt(messages_payload),
        "stream": True,
        "options": {"temperature": temperature},
    }
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
            if exc.response is not None and exc.response.status_code == 404:
                try:
                    yield from _stream_openai_chat_completion(base_url, messages_payload)
                    return
                except Exception as fallback_exc:
                    _raise_user_facing_runtime_error(fallback_exc, generate_url)
        _raise_user_facing_runtime_error(exc, generate_url)


def complete_sync(messages_payload, *, temperature=0.5, max_tokens=60, timeout=30):
    base_url = get_ollama_base_url()

    # External API: đi thẳng vào /v1/chat/completions
    if _use_openai_compat_mode():
        return _complete_openai_chat_sync(
            base_url,
            messages_payload,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )

    # Ollama local: thử /api/chat → /api/generate → fallback /v1/chat/completions
    chat_url = f"{base_url}/api/chat"
    payload = {
        "model": get_ollama_model(),
        "messages": messages_payload,
        "stream": False,
        "options": {"temperature": temperature, "num_predict": max_tokens},
    }
    try:
        response = requests.post(chat_url, json=payload, timeout=timeout)
        response.raise_for_status()
        return ((response.json().get("message") or {}).get("content") or "").strip()
    except requests.exceptions.HTTPError as exc:
        if exc.response is None or exc.response.status_code != 404:
            logger.warning("Auto-title chat request failed: %s", exc)
            return ""
    except Exception as exc:
        logger.warning("Auto-title chat request failed: %s", exc)
        return ""

    generate_url = f"{base_url}/api/generate"
    generate_payload = {
        "model": get_ollama_model(),
        "prompt": _build_generate_prompt(messages_payload),
        "stream": False,
        "options": {"temperature": temperature, "num_predict": max_tokens},
    }
    try:
        response = requests.post(generate_url, json=generate_payload, timeout=timeout)
        response.raise_for_status()
        return (response.json().get("response") or "").strip()
    except Exception as exc:
        if isinstance(exc, requests.exceptions.HTTPError):
            if exc.response is not None and exc.response.status_code == 404:
                return _complete_openai_chat_sync(
                    base_url,
                    messages_payload,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=timeout,
                )
        logger.warning("Auto-title generate request failed: %s", exc)
        return ""


def auto_generate_title(first_user_message: str) -> str:
    messages = [
        {
            "role": "system",
            "content": (
                "Tóm tắt nội dung câu hỏi sau thành một tiêu đề ngắn tối đa 8 từ. "
                "Chỉ trả về tiêu đề bằng tiếng Việt có dấu đầy đủ, không giải thích."
            ),
        },
        {"role": "user", "content": first_user_message},
    ]
    title = complete_sync(messages)
    return title[:200] if title else ""


def check_ai_health() -> tuple[bool, str | None]:
    base_url = get_ollama_base_url()
    if _use_openai_compat_mode():
        url = f"{base_url}/v1/models"
        try:
            response = requests.get(url, headers=_get_auth_headers(), timeout=5)
            response.raise_for_status()
            return True, None
        except Exception as exc:
            logger.warning("AI health check failed: %s", exc)
            return False, "Dịch vụ AI hiện chưa sẵn sàng."

    url = f"{base_url}/api/tags"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return True, None
    except Exception as exc:
        logger.warning("AI health check failed: %s", exc)
        return False, "Dịch vụ AI hiện chưa sẵn sàng."
