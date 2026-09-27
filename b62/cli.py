"""Compose the command-line workflow."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

from .conventions import load_convention
from .errors import GenerationError, GitError
from .generation import DEFAULT_MODEL, build_request, call_api, validate_output
from .git_context import collect_context
from .safety import mask, safe_context

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate commit or PR text from a local Git diff.")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("commit", "pr"):
        command = commands.add_parser(name, help=f"Generate {name} text")
        command.add_argument("--staged", action="store_true", help="Use staged changes")
        command.add_argument("--dry-run", action="store_true",
                             help="Print proposed input locally without API or credential access")
        command.add_argument("--model", default=DEFAULT_MODEL)
        command.add_argument("--temperature", type=float)
        command.add_argument("--max-tokens", type=int)
        command.add_argument("--convention", help="Path to a JSON convention config")
        command.add_argument("--safe-mode", action="store_true")
        command.add_argument("--max-files", type=int, default=10)
        command.add_argument("--max-lines", type=int, default=200)
    args = parser.parse_args(argv)
    if args.temperature is not None and (not math.isfinite(args.temperature) or not 0 <= args.temperature <= 2):
        parser.error("--temperature must be between 0 and 2")
    if args.max_tokens is not None and args.max_tokens < 1:
        parser.error("--max-tokens must be positive")
    if not args.model.strip():
        parser.error("--model must be nonempty")
    if args.max_files < 1 or args.max_lines < 1:
        parser.error("--max-files and --max-lines must be positive")
    try:
        convention = load_convention(args.convention)
    except GenerationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    try:
        context = collect_context(Path.cwd(), args.staged)
    except GitError as exc:
        print(f"Error: {mask(str(exc)) if args.safe_mode else exc}", file=sys.stderr)
        return 2
    if not context["has_changes"]:
        print(f"No {context['selection']} changes to prepare.")
        return 0
    if args.safe_mode:
        context = safe_context(context, args.max_files, args.max_lines)
    proposed_input = {"task": args.command, **context}
    if context["untracked_paths"] and not context["diff"]:
        proposed_input["stage_hint"] = (
            "Only untracked paths are present. Stage the files with git add "
            "to include their contents in a staged diff."
        )
    if context["diff"]:
        proposed_input["request"] = build_request(
            args.command, context, args.model, args.temperature, args.max_tokens, convention)
    if convention:
        proposed_input["convention"] = convention
    if args.dry_run:
        print(json.dumps(proposed_input, ensure_ascii=True, indent=2))
        return 0
    if not context["diff"]:
        print("Error: Only untracked paths are present; stage files to include their contents.",
              file=sys.stderr)
        return 2
    key = os.environ.get("AI_API_KEY") or os.environ.get("OPENAI_API")
    if not key:
        print("Error: Set AI_API_KEY (or OPENAI_API) in the environment.", file=sys.stderr)
        return 2
    try:
        content = call_api(proposed_input["request"], key)
        output = validate_output(args.command, content, str(context["diff"]), convention)
        print(mask(output) if args.safe_mode else output)
    except GenerationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    return 0
