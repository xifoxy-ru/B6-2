"""Collect the selected local Git diff and its paths."""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

from .errors import GitError

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
        code, path = entry[:2], entry[3:]
        item = {"code": code, "path": path}
        if "R" in code or "C" in code:
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
    untracked = [] if staged else [item["path"] for item in status if item["code"] == "??"]
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
        if line.startswith("diff --git "):
            header = line[len("diff --git "):]
            try:
                sides = shlex.split(header)
            except ValueError:
                sides = []
            if len(sides) == 2 and sides[0].startswith("a/") and sides[1].startswith("b/"):
                paths.extend((sides[0][2:], sides[1][2:]))
            elif header.startswith("a/") and " b/" in header:
                left, right = header.rsplit(" b/", 1)
                paths.extend((left[2:], right))
        elif line.startswith(("rename to ", "copy to ")):
            paths.append(line.split(" ", 2)[2])
        elif line.startswith(("+++ b/", "--- a/")):
            paths.append(line[6:])
    return list(dict.fromkeys(paths))
