"""User-facing error categories."""


class GitError(Exception):
    """A local Git command could not provide the requested context."""


class GenerationError(Exception):
    """Generation failed without disclosing response or credential data."""


class OutputFormatError(GenerationError):
    """Generated text has a correctable JSON, field, or length failure."""
