"""Collect the selected local Git diff and its paths."""

from __future__ import annotations

import shlex
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
DIFF_PATH_COUNT = 2
DIFF_FALLBACK_SEPARATOR = " " + DIFF_NEW_PATH_PREFIX
DESTINATION_PREFIXES = ("rename to ", "copy to ")
FILE_HEADER_PREFIXES = ("+++ b/", "--- a/")

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

def changed_paths(diff: str) -> list[str]:
    paths = []
    for line in diff.splitlines():
        if line.startswith(DIFF_HEADER_PREFIX):
            header = line[len(DIFF_HEADER_PREFIX):]
            try:
                sides = shlex.split(header)
            except ValueError:
                sides = []
            if (len(sides) == DIFF_PATH_COUNT
                    and sides[0].startswith(DIFF_OLD_PATH_PREFIX)
                    and sides[1].startswith(DIFF_NEW_PATH_PREFIX)):
                paths.extend((sides[0][len(DIFF_OLD_PATH_PREFIX):],
                              sides[1][len(DIFF_NEW_PATH_PREFIX):]))
            elif header.startswith(DIFF_OLD_PATH_PREFIX) and DIFF_FALLBACK_SEPARATOR in header:
                left, right = header.rsplit(DIFF_FALLBACK_SEPARATOR, 1)
                paths.extend((left[len(DIFF_OLD_PATH_PREFIX):], right))
        elif line.startswith(DESTINATION_PREFIXES):
            prefix = next(prefix for prefix in DESTINATION_PREFIXES if line.startswith(prefix))
            paths.append(line[len(prefix):])
        elif line.startswith(FILE_HEADER_PREFIXES):
            prefix = next(prefix for prefix in FILE_HEADER_PREFIXES if line.startswith(prefix))
            paths.append(line[len(prefix):])
    return list(dict.fromkeys(paths))
