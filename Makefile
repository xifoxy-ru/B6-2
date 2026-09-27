PYTHON ?= python3
PHASE4_TEST_DIR := ../../harness-workspaces/B6-2/phase4/tests
override CACHE_PATHS := __pycache__ b62/__pycache__ .pytest_cache .mypy_cache .ruff_cache

.PHONY: help check clean-cache

help:
	@printf '%s\n' 'Targets:' '  check                  Run Phase 4 aggregate local tests' '  clean-cache            Show local cache paths (dry-run)' '  clean-cache APPLY=1    Remove only listed local cache paths'

check:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m unittest discover -s $(PHASE4_TEST_DIR) -v

clean-cache:
	@for path in $(CACHE_PATHS); do \
		if [ -e "$$path" ] || [ -L "$$path" ]; then \
			if [ -L "$$path" ] || { [ "$$path" = "b62/__pycache__" ] && [ -L b62 ]; }; then printf 'Skipped symlink %s\n' "$$path"; \
			elif [ "$(APPLY)" = "1" ]; then rm -rf -- "$$path"; printf 'Removed %s\n' "$$path"; \
			else printf 'Would remove %s\n' "$$path"; fi; \
		fi; \
	done
	@if [ "$(APPLY)" != "1" ]; then printf '%s\n' 'Dry-run only. Use make clean-cache APPLY=1 to remove these cache paths.'; fi
