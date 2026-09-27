# B6-2 Git text preparation (Phase 1)

Python 3.10+ CLI skeleton for collecting local Git context before future commit-message or pull-request text generation. It uses only the Python standard library at runtime. The `pyproject.toml` is ready for `uv`; no environment setup or package installation is required to run `main.py`.

From a Git repository, run `python3 /Users/sgang/bin/projects/B6-2/main.py commit --dry-run` or replace `commit` with `pr`. The default selection is unstaged changes. Add `--staged` to select the index instead. Dry-run prints proposed API input as JSON, including the selected diff, Git status, and untracked paths. Untracked file contents are not read. If only untracked files are present, the JSON includes a hint to stage them with `git add` so their contents appear in a staged diff. A clean selection prints a no-change message. Outside a repository, the CLI reports an error. Running without `--dry-run` reports that Phase 2 generation is unavailable.

Dry-run stays local: there are no API calls, API-key lookups, or secret-file loading. The generated input may contain secrets already present in tracked diffs, so inspect it before sharing.

`make help` lists maintenance commands. `make check` runs the Phase 1 tests stored outside this product repository. `make clean-cache` previews explicit cache paths at the project root; `make clean-cache APPLY=1` removes only those paths.
