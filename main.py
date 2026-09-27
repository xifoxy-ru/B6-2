"""Local Git context for future commit and pull request generation."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


class GitError(Exception):
    """A local Git command could not provide the requested context."""


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare local Git context for commit or PR text.")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("commit", "pr"):
        command = commands.add_parser(name, help=f"Prepare {name} generation input")
        command.add_argument("--staged", action="store_true", help="Use staged changes")
        command.add_argument(
            "--dry-run", action="store_true",
            help="Print proposed input locally without API or credential access",
        )
    args = parser.parse_args(argv)

    try:
        context = collect_context(Path.cwd(), args.staged)
    except GitError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.dry_run:
        print("Phase 2 generation is unavailable. Use --dry-run to inspect proposed API input.", file=sys.stderr)
        return 2
    if not context["has_changes"]:
        print(f"No {context['selection']} changes to prepare.")
        return 0

    proposed_input = {"task": args.command, **context}
    if context["untracked_paths"] and not context["diff"]:
        proposed_input["stage_hint"] = (
            "Only untracked paths are present. Stage the files with git add "
            "to include their contents in a staged diff."
        )
    print(json.dumps(proposed_input, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
