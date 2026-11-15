# Autonomous AI Code Reviewer & PR Assistant — developer entry points.
# Recipes use tabs. Run `make` or `make help` for the list.

# Interpreter used by `test` and `lint`. Override freely, e.g.
#   make test PYTHON=python3.10
# If `make verify` has already built the verifier venv, prefer it: it is the
# only interpreter guaranteed to have requirements.lock installed.
PYTHON ?= $(if $(wildcard .venv-verify/bin/python),.venv-verify/bin/python,python3)

.PHONY: help verify test lint site run clean

help:
	@echo "make verify  - one-command verifier (venv + lock + pytest + zero-network proof)"
	@echo "make test    - run the test suite: $(PYTHON) -m pytest -q tests"
	@echo "make lint    - syntax/lint check (bash -n on scripts, py_compile on app)"
	@echo "make site    - validate the learning site: python site/tools/validate_lessons.py"
	@echo "make run     - start the webhook server: uvicorn app.main:app --reload --port 8000"
	@echo "make clean   - remove __pycache__, .pytest_cache and .venv-verify"

verify:
	bash scripts/verify.sh

test:
	$(PYTHON) -m pytest -q tests

site:
	$(PYTHON) site/tools/validate_lessons.py

lint:
	bash -n scripts/verify.sh
	$(PYTHON) -m compileall -q app reviewer.py scripts/verify_offline.py

run:
	uvicorn app.main:app --reload --port 8000

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .pytest_cache .venv-verify
