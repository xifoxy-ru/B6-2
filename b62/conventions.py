"""Load the optional title convention."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .errors import GenerationError

TYPES = {"feat", "fix", "docs", "refactor", "test", "chore"}

def load_convention(path: str | None) -> dict[str, str] | None:
    if path is None:
        return None
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        raise GenerationError("Invalid convention config: cannot read a JSON object.") from None
    if not isinstance(data, dict) or set(data) != {"type", "scope", "language", "style"}:
        raise GenerationError("Invalid convention config: expected type, scope, language, style only.")
    if (not isinstance(data["type"], str) or data["type"] not in TYPES
            or not isinstance(data["scope"], str)
            or not re.fullmatch(r"[a-z][a-z0-9-]{0,19}", data["scope"])
            or not isinstance(data["language"], str) or data["language"] not in ("en", "ko")
            or not isinstance(data["style"], str) or data["style"] not in ("lowercase", "sentence")):
        raise GenerationError("Invalid convention config: unsupported selection.")
    return data
