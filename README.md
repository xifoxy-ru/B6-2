# B6-2 Git text generation

Python 3.10+ CLI for generating commit messages and pull request descriptions from a selected local Git diff. It uses only the Python standard library at runtime.

From a Git repository, run `python3 /Users/sgang/bin/projects/B6-2/main.py commit` or replace `commit` with `pr`. The default selection is unstaged tracked changes. Add `--staged` to select the index. Untracked file contents are never read; stage new files to include their contents. A clean selection prints a no-change message without using a key or the network.

Set `AI_API_KEY` in the process environment before generation. `OPENAI_API` is a fallback for the existing local credential naming. The CLI does not load `.env` files. `--model` defaults to `gpt-5-mini`; `--temperature` accepts 0–2 and `--max-tokens` a positive integer. Generation sends one request to `https://copa.codyssey.kr/v1/chat/completions`, with no automatic retry. A commit subject is limited to 72 characters. A PR title is limited to 80 characters and has `Why`, `What`, and `How to Test` bullet sections. The CLI validates the response and reports failure if it remains invalid.

Use `--dry-run` with either command to print the selected Git context and exact proposed request body as JSON, without key lookup or network access. The output can contain secrets already present in a tracked diff; inspect it before sharing. Generated text is based on the diff, and suggested test steps do not claim tests were run.

`make check` runs the Phase 2 external tests. `make clean-cache` previews explicit cache paths at the project root; `make clean-cache APPLY=1` removes only those paths.
