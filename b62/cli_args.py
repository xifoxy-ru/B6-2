"""Build and validate command-line arguments."""

from __future__ import annotations

import argparse
import math

from .generation import DEFAULT_MODEL

SUPPORTED_MODELS = ("gpt-5-mini", "gpt-5.5", "gpt-5.4", "gpt-5.4-mini")
DEFAULT_MAX_FILES = 10
DEFAULT_MAX_LINES = 200
MIN_TEMPERATURE = 0
MAX_TEMPERATURE = 2
MIN_POSITIVE_COUNT = 1


def parse_cli_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate commit or PR text from a local Git diff.")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("commit", "pr"):
        command = commands.add_parser(name, help=f"Generate {name} text")
        command.add_argument("--staged", action="store_true", help="Use staged changes")
        command.add_argument("--dry-run", action="store_true",
                             help="Print proposed input locally without API or credential access")
        command.add_argument("--model", choices=SUPPORTED_MODELS, default=DEFAULT_MODEL)
        command.add_argument("--temperature", type=float)
        command.add_argument("--max-tokens", type=int)
        command.add_argument("--safe-mode", action="store_true")
        command.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES)
        command.add_argument("--max-lines", type=int, default=DEFAULT_MAX_LINES)
    args = parser.parse_args(argv)
    if args.temperature is not None and (
            not math.isfinite(args.temperature)
            or not MIN_TEMPERATURE <= args.temperature <= MAX_TEMPERATURE):
        parser.error("--temperature must be between 0 and 2")
    if args.max_tokens is not None and args.max_tokens < MIN_POSITIVE_COUNT:
        parser.error("--max-tokens must be positive")
    if (args.max_files < MIN_POSITIVE_COUNT
            or args.max_lines < MIN_POSITIVE_COUNT):
        parser.error("--max-files and --max-lines must be positive")
    return args
