"""Retrieve a credential without executing dotenv data or changing the environment."""

from __future__ import annotations

import os
import re
from pathlib import Path

from .errors import GenerationError

_EXPORT_PREFIX = "export"
_KEYS = ("AI_API_KEY", "OPENAI_API")
_ASSIGNMENT = re.compile(r"(AI_API_KEY|OPENAI_API)\b(.*)")
_DOTENV_ERROR = "Cannot read API credentials from the tool .env file."


def _value(text: str) -> str:
    text = text.strip()
    if "\x00" in text:
        raise ValueError
    if text.startswith(("'", '"')):
        quote = text[0]
        end = text.find(quote, 1)
        if end < 0:
            raise ValueError
        tail = text[end + 1:].strip()
        if tail and not tail.startswith("#"):
            raise ValueError
        return text[1:end]
    if "'" in text or '"' in text:
        raise ValueError
    # A hash starts an unquoted comment only after whitespace (or at the start).
    return re.split(r"(?:^|\s)#", text, maxsplit=1)[0].rstrip()


def get_api_key() -> str | None:
    """Prefer existing environment keys, then the tool's own literal .env file."""
    for name in _KEYS:
        if key := os.environ.get(name):
            return key
    dotenv = Path(__file__).resolve().parent.parent / ".env"
    try:
        content = dotenv.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except (OSError, UnicodeError):
        raise GenerationError(_DOTENV_ERROR) from None
    values: dict[str, str] = {}
    try:
        for line in content.splitlines():
            line = line.strip()
            if line.startswith((_EXPORT_PREFIX + " ", _EXPORT_PREFIX + "\t")):
                line = line[len(_EXPORT_PREFIX):].lstrip()
            match = _ASSIGNMENT.fullmatch(line)
            if match is None:
                continue
            name, assignment = match.groups()
            if not assignment.lstrip().startswith("="):
                raise ValueError
            values[name] = _value(assignment.lstrip()[1:])
    except ValueError:
        raise GenerationError(_DOTENV_ERROR) from None
    return next((values[name] for name in _KEYS if values.get(name)), None)
