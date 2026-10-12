"""Compose the command-line workflow."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from .api_client import call_api
from .cli_args import parse_cli_args
from .conventions import load_convention
from .errors import GenerationError, GitError
from .generation import build_request, validate_output
from .git_context import collect_context
from .safety import mask, safe_context

def main(argv: list[str] | None = None) -> int:
    args = parse_cli_args(argv)
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
        output = validate_output(args.command, content, str(context["diff"]), convention,
                                 mask_text=mask if args.safe_mode else None)
        print(output)
    except GenerationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    return 0
