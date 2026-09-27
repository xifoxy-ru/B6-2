# B6-2 Git text generation

Python 3.10+ CLI for generating commit messages and pull request descriptions from a selected local Git diff. It uses only the Python standard library at runtime.

From a Git repository, run `python3 /Users/sgang/bin/projects/B6-2/main.py commit` or replace `commit` with `pr`. The default selection is unstaged tracked changes. Add `--staged` to select the index. Untracked file contents are never read; stage new files to include their contents. A clean selection prints a no-change message without using a key or the network.

Set `AI_API_KEY` in the process environment before generation. `OPENAI_API` is a fallback for the existing local credential naming. The CLI does not load `.env` files. `--model` defaults to `gpt-5-mini`; `--temperature` accepts 0–2 and `--max-tokens` a positive integer. Generation sends one request to `https://copa.codyssey.kr/v1/chat/completions`, with no automatic retry. A commit subject is limited to 72 characters. A PR title is limited to 80 characters and has `Why`, `What`, and `How to Test` bullet sections. The CLI validates the response and reports failure if it remains invalid.

Use `--dry-run` with either command to print the selected Git context and exact proposed request body as JSON, without key lookup or network access. The output can contain secrets already present in a tracked diff; inspect it before sharing. Generated text is based on the diff, and suggested test steps do not claim tests were run.

`--convention path.json` selects an optional convention. The file must contain exactly four string fields, for example:

```json
{"type":"feat","scope":"portfolio","language":"en","style":"lowercase"}
```

`type` is one of `feat`, `fix`, `docs`, `refactor`, `test`, `chore`; `scope` is a lowercase ASCII slug of 1–20 characters, beginning with a letter; `language` is `en` or `ko`; `style` is `lowercase` or `sentence`. The generated commit subject or PR title must begin with `type(scope): `; its description must contain an English letter and no Hangul for `en`, or contain Hangul for `ko`. Its first letter follows the selected case style and it has no final period. These are mechanical checks, not a full language or grammar judgment. The 72-character commit and 80-character PR title limits still apply, as do the PR bullet sections. Missing, malformed, or unsupported config fails before credential lookup or network access. Without this option the original format is used.

This example is inspired by a read-only look at B4-1's Git subjects: some use `feat:`, `fix:`, `docs:`, and `refactor`, while others are plain English phrases. Its README describes a portfolio project. B4-1 does not declare this JSON schema or a formal commit rule; `portfolio` and the style choice are examples for this tool.

`--safe-mode` masks common fake API key (`sk-...`), `api_key=`, `token=`, `password=`, and email patterns in the selected diff and visible paths before creating the request or preview. It also masks generated text and Git errors. Regex masking reduces exposure but cannot guarantee secrecy; inspect results before sharing. In safe mode, status entries are omitted from the preview so they cannot disclose paths outside the bounded diff. `--max-files` and `--max-lines` are positive limits, defaulting to 10 and 200. They apply to the selected tracked Git diff in safe mode: a file is a `diff --git` section, and a line is a physical diff line including headers, metadata, hunk lines, and binary patch lines. Sections are taken in order, with at most the remaining line budget from the final included section. The preview and API request use the same bounded diff and paths derived from it. `truncation` reports total, included, and dropped file sections and physical lines; a partially included final section counts as included, with its omitted lines counted as dropped. At most `max-files` untracked path names are displayed separately, with their dropped count. Untracked contents remain excluded. Renames, binary patches, and mode changes follow the same section and line rules. A very low line limit can leave only a file header; omitted content must not be inferred.

Synthetic illustration, with no real credential: if a tracked diff contains `+token=FAKE_TOKEN`, `commit --dry-run` shows that placeholder, while `commit --dry-run --safe-mode` shows `+token=[REDACTED_SECRET]` in both the preview diff and proposed request. Safe mode also reports any dropped lines or files.

`main.py` is the entrypoint. The `b62` package separates local Git collection (`git_context`), masking and diff bounds (`safety`), convention loading (`conventions`), AI request and validation (`generation`), and CLI flow (`cli`).

`make check` runs one Phase 4 aggregate suite containing copies of the earlier external behavior tests and module/subprocess checks. `make clean-cache` previews explicit cache paths at the project root and in `b62`; `make clean-cache APPLY=1` removes only regular listed paths and skips symlinks.
