"""Save the two safe-mode diffs locally without changing request construction."""

from __future__ import annotations

import os
from pathlib import Path
import stat

from .errors import GenerationError, GitError
from .git_context import git

OUTPUT_DIRECTORY = "safe-mode-output"
_OUTPUT_NAMES = (".gitignore", "before", "after")
_IGNORE_CONTENT = b"*\n"
_SAVE_ERROR = "Cannot save safe-mode diff files safely. No API request was sent."


def _owned(info: os.stat_result) -> bool:
    return not hasattr(os, "getuid") or info.st_uid == os.getuid()


def _open_file(directory: int, name: str) -> int:
    # Reject special files before opening them (and check the opened inode too).
    try:
        existing = os.stat(name, dir_fd=directory, follow_symlinks=False)
    except FileNotFoundError:
        pass
    else:
        if not stat.S_ISREG(existing.st_mode) or existing.st_nlink != 1 or not _owned(existing):
            raise OSError("Unsafe output file")
    # Do not truncate until every destination has passed the safety checks.
    descriptor = os.open(name, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK,
                         0o600, dir_fd=directory)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or not _owned(info):
            raise OSError("Unsafe output file")
        os.fchmod(descriptor, 0o600)
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _write(descriptor: int, content: bytes) -> None:
    os.lseek(descriptor, 0, os.SEEK_SET)
    os.ftruncate(descriptor, 0)
    with os.fdopen(os.dup(descriptor), "wb") as stream:
        stream.write(content)


def save_safe_mode_diffs(repository: Path, before: str, after: str) -> None:
    """Replace private, ignored diff files; refuse tracked or unsafe targets."""
    descriptors: list[int] = []
    try:
        if (git(repository, "ls-files", "-z", "--", OUTPUT_DIRECTORY)
                or git(repository, "diff", "--cached", "--name-only", "--no-ext-diff",
                       "--no-textconv", "--", OUTPUT_DIRECTORY)):
            raise OSError("Tracked output path")
        # Directory-relative no-follow opens keep writes inside the opened folder.
        root = os.open(repository, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        descriptors.append(root)
        try:
            os.mkdir(OUTPUT_DIRECTORY, 0o700, dir_fd=root)
        except FileExistsError:
            pass
        directory = os.open(OUTPUT_DIRECTORY, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                            dir_fd=root)
        descriptors.append(directory)
        if not _owned(os.fstat(directory)) or set(os.listdir(directory)) - set(_OUTPUT_NAMES):
            raise OSError("Unsafe output directory")
        os.fchmod(directory, 0o700)
        output_files = {}
        for name in _OUTPUT_NAMES:
            descriptor = _open_file(directory, name)
            descriptors.append(descriptor)
            output_files[name] = descriptor
        # Read one extra byte: accept only an empty file or exactly our ignore line.
        if os.read(output_files[".gitignore"], len(_IGNORE_CONTENT) + 1) not in (b"", _IGNORE_CONTENT):
            raise OSError("Unexpected output ignore file")
        _write(output_files[".gitignore"], _IGNORE_CONTENT)
        _write(output_files["before"], before.encode("utf-8", errors="surrogateescape"))
        _write(output_files["after"], after.encode("utf-8", errors="surrogateescape"))
    except (OSError, GitError, UnicodeError, AttributeError, NotImplementedError):
        raise GenerationError(_SAVE_ERROR) from None
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)
