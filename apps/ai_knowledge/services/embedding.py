from __future__ import annotations

import logging
import time
from urllib.parse import urlparse

import requests
from django.conf import settings


logger = logging.getLogger(__name__)


def _is_loopback_url(url: str) -> bool:
    hostname = urlparse((url or "").strip()).hostname
    return hostname in {"127.0.0.1", "localhost", "::1"}


def get_embedding_provider() -> str:
    return getattr(settings, "AI_EMBED_PROVIDER", "ollama").strip().lower()


def get_embedding_base_url() -> str:
    # AI_EMBED_BASE_URL luôn được ưu tiên tuyệt đối — không fallback sang chat URL
    embed_url = getattr(settings, "AI_EMBED_BASE_URL", "").strip()
    if embed_url:
        return embed_url.rstrip("/")
    ollama_url = getattr(settings, "OLLAMA_BASE_URL", "").strip()
    return (ollama_url or "http://127.0.0.1:11434").rstrip("/")


def get_embedding_model() -> str:
    return getattr(settings, "AI_EMBED_MODEL", "nomic-embed-text").strip()


def get_embedding_dimensions() -> int:
    return int(getattr(settings, "AI_EMBED_DIMENSIONS", 768))


def get_embedding_timeout() -> int:
    return int(getattr(settings, "AI_TIMEOUT", 120))


def _post_embed_request(url: str, payload: dict, timeout: int) -> requests.Response:
    response = requests.post(url, json=payload, timeout=timeout)
    response.raise_for_status()
    return response


def _normalize_embedding(value: list[float] | None) -> list[float]:
    if not value:
        raise RuntimeError("Embedding provider did not return a usable vector.")
    normalized = [float(item) for item in value]
    expected = get_embedding_dimensions()
    if len(normalized) != expected:
        raise RuntimeError(
            f"Embedding dimensions mismatch: got={len(normalized)} expected={expected}"
        )
    return normalized


def _embed_with_ollama(texts: list[str]) -> list[list[float]]:
    base_url = get_embedding_base_url()
    model = get_embedding_model()
    if not model:
        raise RuntimeError("AI_EMBED_MODEL is not configured.")

    timeout = get_embedding_timeout()
    last_error = None
    for attempt in range(2):
        try:
            response = _post_embed_request(
                f"{base_url}/api/embed",
                {"model": model, "input": texts},
                timeout=timeout,
            )
            data = response.json()
            embeddings = data.get("embeddings") or []
            if len(embeddings) != len(texts):
                raise RuntimeError("Embedding batch size mismatch.")
            return [_normalize_embedding(item) for item in embeddings]
        except requests.HTTPError as exc:
            last_error = exc
            if exc.response is None or exc.response.status_code != 404:
                logger.warning("Embed /api/embed failed: %s", exc)
                if attempt == 0:
                    time.sleep(0.25)
                    continue
                raise
        except Exception as exc:
            last_error = exc
            logger.warning("Embed batch attempt failed: %s", exc)
            if attempt == 0:
                time.sleep(0.25)
                continue
            raise

    embeddings: list[list[float]] = []
    for text in texts:
        response = _post_embed_request(
            f"{base_url}/api/embeddings",
            {"model": model, "prompt": text},
            timeout=timeout,
        )
        data = response.json()
        embeddings.append(_normalize_embedding(data.get("embedding")))
    if not embeddings and last_error is not None:
        raise last_error
    return embeddings


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    provider = get_embedding_provider()
    if provider in {"ollama", "local", "openai-compatible"}:
        return _embed_with_ollama(texts)
    if provider == "sentence_transformers":
        raise RuntimeError(
            "sentence_transformers provider is not installed in this environment."
        )
    raise RuntimeError(f"Unsupported AI_EMBED_PROVIDER: {provider}")


def embed_text(text: str) -> list[float]:
    return embed_texts([text])[0]
