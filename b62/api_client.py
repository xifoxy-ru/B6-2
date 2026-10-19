"""Transport AI requests and decode API responses."""

from __future__ import annotations

import json
from http import HTTPStatus
from http.client import HTTPException
import urllib.error
import urllib.request

from .errors import GenerationError

API_URL = "https://copa.codyssey.kr/v1/chat/completions"
TIMEOUT_SECONDS = 30

def call_api(payload: dict[str, object], key: str) -> str:
    body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    request = urllib.request.Request(
        API_URL, data=body, method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        if exc.code in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
            raise GenerationError("Authentication failed (HTTP 401/403). Check the API key.") from None
        if exc.code == HTTPStatus.TOO_MANY_REQUESTS:
            raise GenerationError("Quota or rate limit exceeded (HTTP 429).") from None
        raise GenerationError(f"API request failed (HTTP {exc.code}).") from None
    except (TimeoutError, OSError) as exc:
        if isinstance(exc, TimeoutError) or "timed out" in str(exc).lower():
            raise GenerationError("API request timed out.") from None
        raise GenerationError("Network error while contacting the API.") from None
    except HTTPException:
        raise GenerationError("HTTP protocol error while reading the API response.") from None
    try:
        response = json.loads(raw)
        content = response["choices"][0]["message"]["content"]
        if not isinstance(content, str):
            raise ValueError
        return content
    except (ValueError, KeyError, IndexError, TypeError):
        raise GenerationError("Malformed API response.") from None
