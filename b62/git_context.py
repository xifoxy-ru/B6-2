"""Collect the selected local Git diff and its paths."""

from __future__ import annotations

import subprocess
from pathlib import Path

from .errors import GitError

STATUS_RENAMED = "R"
STATUS_COPIED = "C"
STATUS_UNTRACKED = "??"
PORCELAIN_STATUS_WIDTH = 2
PORCELAIN_PATH_OFFSET = PORCELAIN_STATUS_WIDTH + len(" ")
DIFF_HEADER_PREFIX = "diff --git "
DIFF_OLD_PATH_PREFIX = "a/"
DIFF_NEW_PATH_PREFIX = "b/"
RENAME_PATH_PREFIXES = ("rename from ", "rename to ", "copy from ", "copy to ")
FILE_HEADER_PREFIXES = ("+++ ", "--- ")
GIT_QUOTED_ESCAPES = {"a": 7, "b": 8, "t": 9, "n": 10, "v": 11, "f": 12,
                      "r": 13, "\\": 92, '"': 34}
GIT_OCTAL_DIGITS = "01234567"
GIT_OCTAL_WIDTH = 3

def git(cwd: Path, *args: str) -> bytes:
    command = ["git", "-c", "core.quotepath=false", *args]
    try:
        result = subprocess.run(
            command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as exc:
        raise GitError(f"Cannot run Git: {exc}") from exc
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise GitError(detail or f"Git exited with status {result.returncode}")
    return result.stdout

def git_text(cwd: Path, *args: str) -> str:
    return git(cwd, *args).decode("utf-8", errors="surrogateescape")

def status_entries(raw: bytes) -> list[dict[str, str]]:
    entries = raw.decode("utf-8", errors="surrogateescape").split("\0")
    result = []
    index = 0
    while index < len(entries) and entries[index]:
        entry = entries[index]
        # Porcelain v1 records contain an XY status, one space, then the path.
        code, path = entry[:PORCELAIN_STATUS_WIDTH], entry[PORCELAIN_PATH_OFFSET:]
        item = {"code": code, "path": path}
        if STATUS_RENAMED in code or STATUS_COPIED in code:
            # With -z, rename/copy records put the original path in the next entry.
            index += 1
            item["original_path"] = entries[index]
        result.append(item)
        index += 1
    return result

def collect_context(cwd: Path, staged: bool) -> dict[str, object]:
    try:
        root = Path(git_text(cwd, "rev-parse", "--show-toplevel").strip())
    except GitError as exc:
        raise GitError("The current directory is not inside a Git repository.") from exc

    status = status_entries(git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all"))
    diff_args = ["diff", "--no-ext-diff", "--no-textconv", "--binary"]
    if staged:
        diff_args.append("--cached")
    diff = git_text(root, *diff_args)
    untracked = [] if staged else [item["path"] for item in status if item["code"] == STATUS_UNTRACKED]
    return {
        "repository": str(root),
        "selection": "staged" if staged else "unstaged",
        "status": status,
        "diff": diff,
        "untracked_paths": untracked,
        "has_changes": bool(diff or untracked),
    }

def _decode_git_path(value: str) -> str | None:
    """Decode one whole Git path, whose C escapes represent UTF-8 bytes."""
    if not value.startswith('"'):
        return value if '"' not in value and "\\" not in value else None
    decoded = bytearray()
    index = 1
    while index < len(value):
        char = value[index]
        if char == '"':
            if index != len(value) - 1:
                return None
            return decoded.decode("utf-8", errors="surrogateescape")
        if char != "\\":
            decoded.extend(char.encode("utf-8", errors="surrogateescape"))
            index += 1
            continue
        index += 1
        if index >= len(value):
            return None
        escape = value[index]
        if escape in GIT_QUOTED_ESCAPES:
            decoded.append(GIT_QUOTED_ESCAPES[escape])
            index += 1
        else:
            octal = value[index:index + GIT_OCTAL_WIDTH]
            if (len(octal) != GIT_OCTAL_WIDTH
                    or any(digit not in GIT_OCTAL_DIGITS for digit in octal)
                    or int(octal, 8) > 255):
                return None
            decoded.append(int(octal, 8))
            index += GIT_OCTAL_WIDTH
    return None


def _diff_header_paths(header: str) -> list[str]:
    # Spaces in unquoted Git paths are literal. Consider only separators whose
    # two complete sides decode with the expected prefixes, never shell words.
    candidates = []
    for index, char in enumerate(header):
        if char != " " or not header[index + 1:].startswith(("b/", '"b/')):
            continue
        old = _decode_git_path(header[:index])
        new = _decode_git_path(header[index + 1:])
        if (old is not None and new is not None
                and old.startswith(DIFF_OLD_PATH_PREFIX)
                and new.startswith(DIFF_NEW_PATH_PREFIX)):
            candidates.append([old[len(DIFF_OLD_PATH_PREFIX):],
                               new[len(DIFF_NEW_PATH_PREFIX):]])
    # An ambiguous rename needs its separate rename or file headers. A safe
    # truncation must not invent paths from an ambiguous header alone.
    return candidates[0] if len(candidates) == 1 else []


def changed_paths(diff: str) -> list[str]:
    paths = []
    in_header = False
    for line in diff.split("\n"):
        if line.startswith(DIFF_HEADER_PREFIX):
            in_header = True
            paths.extend(_diff_header_paths(line[len(DIFF_HEADER_PREFIX):]))
        elif line.startswith(("@@", "GIT binary patch")):
            in_header = False
        elif not in_header:
            continue
        elif line.startswith(RENAME_PATH_PREFIXES):
            prefix = next(prefix for prefix in RENAME_PATH_PREFIXES if line.startswith(prefix))
            path = _decode_git_path(line[len(prefix):])
            if path is not None:
                paths.append(path)
        elif line.startswith(FILE_HEADER_PREFIXES):
            value = line[len(FILE_HEADER_PREFIXES[0]):]
            # Git appends a tab separator to unquoted spaced file headers.
            # A real tab in a filename is C-quoted, so remove only this marker.
            if not value.startswith('"') and value.endswith("\t"):
                value = value[:-1]
            path = _decode_git_path(value)
            if path is not None and path.startswith((DIFF_OLD_PATH_PREFIX, DIFF_NEW_PATH_PREFIX)):
                paths.append(path[len(DIFF_OLD_PATH_PREFIX):])
    return list(dict.fromkeys(paths))
