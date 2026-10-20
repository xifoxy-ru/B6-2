PYTHON ?= python3
CLI := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))main.py)
REPO ?= $(CURDIR)
override CACHE_PATHS := __pycache__ b62/__pycache__ .pytest_cache .mypy_cache .ruff_cache

.PHONY: help check clean commit pr preview-commit preview-pr

help:
	@printf '%s\n' 'Targets:' '  commit                 Generate commit text for REPO' '  pr                     Generate PR text for REPO' '  preview-commit         Show commit request JSON locally' '  preview-pr             Show PR request JSON locally' '  check                  Run local syntax/import/help smoke checks' '  clean                  Remove only listed local cache paths' 'Options: REPO=target-directory ARGS="--staged ..."'

commit pr preview-commit preview-pr:
	@cd "$(REPO)" && PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -B "$(CLI)" $(if $(filter commit preview-commit,$@),commit,pr) $(if $(filter preview-commit preview-pr,$@),--dry-run) $(ARGS)

check:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -B -c 'from pathlib import Path; files = [Path("main.py"), *Path("b62").glob("*.py")]; [compile(path.read_bytes(), str(path), "exec") for path in files]; print(f"Syntax OK: {len(files)} files")'
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -B -c 'import main, b62.cli, b62.errors, b62.generation, b62.git_context, b62.safety; print("Imports OK")'
	@PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -B main.py --help > /dev/null
	@PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -B main.py commit --help > /dev/null
	@PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -B main.py pr --help > /dev/null
	@printf '%s\n' 'CLI help OK'

clean:
	@for path in $(CACHE_PATHS); do \
		if [ -e "$$path" ] || [ -L "$$path" ]; then \
			if [ -L "$$path" ] || { [ "$$path" = "b62/__pycache__" ] && [ -L b62 ]; }; then printf 'Skipped symlink %s\n' "$$path"; \
			else rm -rf -- "$$path" || exit $$?; printf 'Removed %s\n' "$$path"; fi; \
		fi; \
	done
