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
_FILE_WORD = re.compile(r"\bfile\b", re.IGNORECASE)
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
    else:
        if set(data) != {"title", "why", "what", "how_to_test"}:
            raise OutputFormatError("Invalid generated PR fields.")
        title = _single_line(data["title"], "title", PR_TITLE_LIMIT)
        why = _items(data["why"], "Why")
        what = _items(data["what"], "What")
        how = _items(data["how_to_test"], "How to Test")
        grounding = " ".join(what)
        output = "\n".join([title, "", "## Why", *[f"- {x}" for x in why],
                            "", "## What", *[f"- {x}" for x in what],
                            "", "## How to Test", *[f"- {x}" for x in how]])
    # Ground against the same control-whitespace rendering as generated text.
    # Ordinary spaces in filenames remain meaningful.
    rendered_paths = [_CONTROL_WHITESPACE.sub(" ", path) for path in paths]
    path_names = [_CONTROL_WHITESPACE.sub(" ", Path(path).name) for path in paths]
    if task == "commit":
        fits = [name for name in path_names if len(name) <= COMMIT_SUBJECT_LIMIT]
        grounded = (any(name and name in grounding for name in fits)
                    if fits else bool(_FILE_WORD.search(grounding)))
    else:
        grounded = any(path and path in grounding for path in rendered_paths)
    if not grounded:
        raise GenerationError("Invalid generated output: no changed file referenced.")
    if _UNSUPPORTED_TEST_CLAIM.search(output):
        raise GenerationError("Invalid generated output: unsupported test-result claim.")
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
