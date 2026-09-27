"""Mask sensitive patterns and bound a selected diff."""

from __future__ import annotations

import re

from .git_context import changed_paths

ASSIGNMENT_MASK = re.compile(
    r"""\b(?P<prefix>(?:api[_-]?key|token|password)['"]?[ \t]*[:=][ \t]*)
         (?P<value>"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[^\s,;"']+)""",
    re.I | re.X,
)
MASKS = (
    (re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"), "[REDACTED_API_KEY]"),
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
     "[REDACTED_EMAIL]"),
)



def mask(value: str) -> str:
    def replace_assignment(match: re.Match[str]) -> str:
        found = match.group("value")
        quote = found[0] if found[0] in ("'", '"') else ""
        return match.group("prefix") + quote + "[REDACTED_SECRET]" + quote

    value = ASSIGNMENT_MASK.sub(replace_assignment, value)
    for pattern, replacement in MASKS:
        value = pattern.sub(replacement, value)
    return value

def bounded_diff(diff: str, max_files: int, max_lines: int) -> tuple[str, dict[str, int]]:
    lines = diff.splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if line.startswith("diff --git ")]
    if not starts and lines:
        starts = [0]
    chunks = [lines[start:end] for start, end in zip(starts, starts[1:] + [len(lines)])]
    kept: list[str] = []
    kept_files = 0
    used_lines = 0
    dropped_files = 0
    dropped_lines = 0
    for chunk in chunks:
        if kept_files >= max_files or used_lines >= max_lines:
            dropped_files += 1
            dropped_lines += len(chunk)
            continue
        take = min(len(chunk), max_lines - used_lines)
        kept.extend(chunk[:take])
        used_lines += take
        kept_files += 1
        dropped_lines += len(chunk) - take
    return "".join(kept), {"total_files": len(chunks), "included_files": kept_files,
                            "dropped_files": dropped_files, "total_lines": len(lines),
                            "included_lines": used_lines, "dropped_lines": dropped_lines}

def safe_context(context: dict[str, object], max_files: int, max_lines: int) -> dict[str, object]:
    # Sanitize before splitting so dropped sections cannot leak through metadata.
    diff, counts = bounded_diff(mask(str(context["diff"])), max_files, max_lines)
    untracked = [mask(p) for p in context["untracked_paths"]]
    untracked_kept = untracked[:max_files]
    counts["untracked_paths_dropped"] = len(untracked) - len(untracked_kept)
    return {"repository": mask(str(context["repository"])),
            "selection": context["selection"], "diff": diff,
            "changed_paths": changed_paths(diff), "untracked_paths": untracked_kept,
            "truncation": counts, "has_changes": context["has_changes"]}
