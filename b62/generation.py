"""Build AI requests and validate generated output."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path

from .api_client import call_api
from .errors import GenerationError, OutputFormatError
from .git_context import changed_paths
from .limits import (COMMIT_SUBJECT_LIMIT, GENERATION_ATTEMPT_LIMIT,
                     PR_ITEM_LIMIT, PR_TITLE_LIMIT)
from .prompts import format_correction_message, system_message

DEFAULT_MODEL = "gpt-5-mini"

_CONTROL_WHITESPACE = re.compile(r"[\r\n\t\f\v\u2028\u2029]+")
_KOREAN_TEST_CLAIM = re.compile(
    r"(?:테스트|검증|검사)[^.!?\n]{0,30}?(?:"
    r"(?:통과|성공|완료)(?:했습니다|하였습니다|했다|하였다|했음|함|"
    r"되었습니다|됐습니다|되었다|됐다|되었음|됨)"
    r"|(?:실행|수행|확인)(?:했습니다|하였습니다|했다|하였다|했음|함)"
    r"|돌렸습니다|돌렸다|돌렸음|돌림"
    r"|(?:통과|성공|완료)(?=[.!?\n]|$)"
    r"|(?:실행|수행)한\s+결과\s+[^.!?\n]{0,30}?(?:"
    r"정상(?:입니다|이었다|이었습니다)|(?:문제|오류)가?\s*없(?:습니다|었다|었습니다)))"
    r"(?=$|[\s.!?,])"
    r"|(?:검증|검사)(?:했습니다|하였습니다|했다|하였다|했음|함|됨|"
    r"되었습니다|됐습니다)(?=$|[\s.!?,])"
)
_TECHNICAL_CODE = re.compile(r"`(?:[^`\s]+|(?:git|make|python3?|pytest) [^`\n]+)`")
_TECHNICAL_NAMES = re.compile(
    r"\[REDACTED_(?:SECRET|EMAIL|API_KEY)\]|"
    r"\b(?:Git|Python|JSON|API|CLI|HTTP|UTF|ASCII|PR|URL|[A-Z][a-z]+(?:[A-Z][A-Za-z0-9]*)+)\b"
)
_MIN_KOREAN_LETTERS = 2
_MIN_KOREAN_SHARE = 0.6
_UNSUPPORTED_TEST_CLAIM = re.compile(
    r"\b(?:tests? (?:passed|ran|were run|succeeded)|verified|validation passed|"
    r"all checks pass(?:ed)?)\b", re.IGNORECASE
)

def build_request(task: str, context: dict[str, object], model: str,
                  temperature: float | None, max_tokens: int | None) -> dict[str, object]:
    diff = str(context["diff"])
    paths = changed_paths(diff)
    system = system_message(task, "truncation" in context)
    user = json.dumps({"selection": context["selection"], "changed_paths": paths,
                       "diff": diff,
                       **({"truncation": context["truncation"]} if "truncation" in context else {})},
                      ensure_ascii=True)
    request: dict[str, object] = {
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
    }
    if temperature is not None:
        request["temperature"] = temperature
    if max_tokens is not None:
        request["max_tokens"] = max_tokens
    return request

def _single_line(value: object, label: str, limit: int) -> str:
    if not isinstance(value, str):
        raise OutputFormatError(f"Invalid generated {label}: expected text.")
    value = _CONTROL_WHITESPACE.sub(" ", value).strip()
    if not value or len(value) > limit:
        raise OutputFormatError(f"Invalid generated {label}: empty or exceeds {limit} characters.")
    return value

def _items(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise OutputFormatError(f"Invalid generated {label}: expected nonempty list.")
    return [_single_line(item, label, PR_ITEM_LIMIT) for item in value]

def _without_changed_paths(value: str, paths: list[str]) -> str:
    prose = value
    # Allow actual paths/basenames even when followed by Korean particles.
    names = set(paths) | {Path(path).name for path in paths}
    for name in sorted(names, key=len, reverse=True):
        if name:
            prose = re.sub(r"(?<![A-Za-z0-9_])" + re.escape(name)
                           + r"(?![A-Za-z0-9_])", "", prose)
    return prose


def _require_korean(value: str, paths: list[str], diff: str,
                    allow_command: bool = False) -> None:
    """Check prose conservatively, not a full language or meaning detector."""
    if (allow_command and value.startswith("`") and value.endswith("`")
            and re.fullmatch(r"(?:git|make|python3?|pytest) [^`\n]+", value[1:-1])
            and value[1:-1] in diff):
        return
    prose = _without_changed_paths(value, paths)
    prose = _TECHNICAL_NAMES.sub("", _TECHNICAL_CODE.sub("", prose))
    letters = [char for char in prose if char.isalpha()]
    korean = sum("가" <= char <= "힣" for char in letters)
    if (korean < _MIN_KOREAN_LETTERS
            or korean < len(letters) * _MIN_KOREAN_SHARE):
        raise OutputFormatError("Invalid generated output: expected Korean prose.")


def validate_output(task: str, content: str, diff: str,
                    mask_text=None) -> str:
    try:
        data = json.loads(content)
    except (ValueError, TypeError):
        raise OutputFormatError("Invalid generated output: expected a JSON object.") from None
    if not isinstance(data, dict):
        raise OutputFormatError("Invalid generated output: expected a JSON object.")
    if mask_text is not None:
        data = {key: (mask_text(value) if isinstance(value, str) else
                      [mask_text(item) if isinstance(item, str) else item for item in value]
                      if isinstance(value, list) else value)
                for key, value in data.items()}
    paths = changed_paths(diff)
    if task == "commit":
        if set(data) != {"subject"}:
            raise OutputFormatError("Invalid generated commit fields.")
        subject = _single_line(data["subject"], "subject", COMMIT_SUBJECT_LIMIT)
        output = subject
        grounding = subject
        prose_items = [subject]
        proposed_steps = []
    else:
        if set(data) != {"title", "why", "what", "how_to_test"}:
            raise OutputFormatError("Invalid generated PR fields.")
        title = _single_line(data["title"], "title", PR_TITLE_LIMIT)
        why = _items(data["why"], "Why")
        what = _items(data["what"], "What")
        how = _items(data["how_to_test"], "How to Test")
        grounding = " ".join(what)
        prose_items = [title, *why, *what]
        proposed_steps = how
        output = "\n".join([title, "", "## 변경 이유", *[f"- {x}" for x in why],
                            "", "## 변경 내용", *[f"- {x}" for x in what],
                            "", "## 테스트 방법", *[f"- {x}" for x in how]])
    # Ground against the same control-whitespace rendering as generated text.
    # Ordinary spaces in filenames remain meaningful.
    rendered_paths = [_CONTROL_WHITESPACE.sub(" ", path) for path in paths]
    path_names = [_CONTROL_WHITESPACE.sub(" ", Path(path).name) for path in paths]
    if task == "commit":
        fits = [name for name in path_names if len(name) <= COMMIT_SUBJECT_LIMIT]
        grounded = (any(name and name in grounding for name in fits)
                    if fits else "파일" in grounding)
    else:
        grounded = any(path and path in grounding for path in rendered_paths)
    if not grounded:
        raise GenerationError("Invalid generated output: no changed file referenced.")
    claim_text = _TECHNICAL_CODE.sub("", _without_changed_paths(output, rendered_paths))
    if (_UNSUPPORTED_TEST_CLAIM.search(output)
            or _KOREAN_TEST_CLAIM.search(claim_text)):
        raise GenerationError("Invalid generated output: unsupported test-result claim.")
    for item in prose_items:
        _require_korean(item, rendered_paths, diff)
    for item in proposed_steps:
        _require_korean(item, rendered_paths, diff, allow_command=True)
    return output


def generate_validated_output(
        task: str, request: dict[str, object], key: str, diff: str,
        mask_text=None,
        api_call: Callable[[dict[str, object], str], str] | None = None) -> str:
    """Regenerate a format failure once; transport and semantic failures stop."""
    transport = call_api if api_call is None else api_call
    attempt_request = request
    for attempt in range(GENERATION_ATTEMPT_LIMIT):
        # Transport errors are outside the validation catch and never retried.
        content = transport(attempt_request, key)
        try:
            return validate_output(task, content, diff, mask_text)
        except OutputFormatError:
            if attempt + 1 == GENERATION_ATTEMPT_LIMIT:
                raise
            # Preserve the original request and omit all rejected response text.
            attempt_request = deepcopy(request)
            attempt_request["messages"].append(
                {"role": "user", "content": format_correction_message()})
    raise AssertionError("Generation attempt limit must be positive.")
