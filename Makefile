# Thin wrapper. Every target calls `python -m lineguard`, which also runs
# without make (see docs/umsetzung.md, rule 7).
PY ?= .venv/bin/python
PACK ?= soony_gh6

.PHONY: install init run ui test lint eval demo-reset
install:
	python3 -m venv .venv && $(PY) -m pip install -e ".[dev]"
init:
	$(PY) -m lineguard init
run:
	$(PY) -m lineguard run
ui:
	cd web && npm run dev
test:
	$(PY) -m pytest -q
lint:
	$(PY) -m ruff check lineguard tests
eval:
	$(PY) -m lineguard eval $(PACK)
demo-reset:
	$(PY) -m lineguard demo-reset
