"""Build and validate command-line arguments."""

from __future__ import annotations

import argparse
import math

from .generation import DEFAULT_MODEL


def parse_cli_args(argv: list[str] | None = None) -> argparse.Namespace:
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
    return args
