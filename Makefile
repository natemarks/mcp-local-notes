.DEFAULT_GOAL := help
SHELL := $(shell which bash)

IMAGE := mcp-local-notes
ENV_FILE := .env.json

# Reads one key out of .env.json via python3 (no jq dependency, since
# python3 is already required by this whole project), falling back to
# $(2) if the file or the key is missing. `make start FOO=bar` on the
# command line still overrides either source: a `?=` below never even
# runs this shell-out when the variable is already set that way.
#
# Deliberately not a call into core.config.load_env_file: Make needs
# these values before .venv/the package even exist (this IS what builds
# them), so it can't import project code -- hence this small, separate
# read of the same file, kept intentionally minimal (one dict.get with
# a fallback) to limit how far the two can drift.
env_json_get = python3 -c "import json, os; f = '$(ENV_FILE)'; d = json.load(open(f, encoding='utf-8')) if os.path.exists(f) else {}; print(d.get('$(1)', '$(2)'))"

MCP_BIND_HOST ?= $(shell $(call env_json_get,MCP_BIND_HOST,127.0.0.1))
MCP_PORT ?= $(shell $(call env_json_get,MCP_PORT,8000))
NOTES_DIR ?= $(shell $(call env_json_get,NOTES_DIR,./notes))

help: ## Show this help
	@fgrep -h "##" $(MAKEFILE_LIST) | fgrep -v fgrep | sed -e 's/\\$$//' | sed -e 's/##//'

.venv: ## create venv if it doesn't exist
	python3 -m venv .venv
	source .venv/bin/activate && pip install --upgrade pip setuptools
	source .venv/bin/activate && pip install -r requirements.txt
	source .venv/bin/activate && pip install -e .

clean-venv: clean-cache ## re-create virtual env
	[[ -e .venv ]] && rm -rf .venv
	$(MAKE) .venv

black: .venv ## format python files
	source .venv/bin/activate && git ls-files '*.py' | xargs black --line-length=79

black-check: .venv ## check python formatting without modifying
	source .venv/bin/activate && git ls-files '*.py' | xargs black --check --line-length=79

pylint: .venv ## lint python files
	source .venv/bin/activate && git ls-files '*.py' | xargs pylint --max-line-length=90

mypy: .venv ## type check python files
	source .venv/bin/activate && git ls-files '*.py' | xargs python3 -m mypy

shellcheck: ## check shell scripts
	@if git ls-files 'scripts/*.sh' | grep -q .; then \
		git ls-files 'scripts/*.sh' | xargs shellcheck --severity=error --format=gcc; \
	fi

unit: .venv ## run unit tests
	source .venv/bin/activate && python3 -m pytest -v -m "unit" tests/

unit-update-golden: .venv ## update golden files
	source .venv/bin/activate && python3 -m pytest -v -m "unit" tests/ --update_golden

integration: .venv ## run integration tests (requires credentials)
	source .venv/bin/activate && python3 -m pytest -v -m "integration" tests/

static-check: black-check mypy shellcheck pylint unit ## run all static checks (CI)

static: black mypy shellcheck pylint unit ## run all static checks with auto-format

clean-cache: ## clean python and pytest cache data
	@find . -type f -name "*.py[co]" -delete -not -path "./.venv/*"
	@find . -type d -name __pycache__ -not -path "./.venv/*" -exec rm -rf {} + 2>/dev/null || true
	@rm -rf .pytest_cache

build: ## build the docker image
	docker build -t $(IMAGE) .

start: build ## run the MCP server as a background container
	mkdir -p $(NOTES_DIR)
	docker run -d --name $(IMAGE) \
		-v $(abspath $(NOTES_DIR)):/notes \
		-p $(MCP_BIND_HOST):$(MCP_PORT):8000 \
		$(IMAGE)

stop: ## stop and remove the running container
	docker stop $(IMAGE)
	docker rm $(IMAGE)

logs: ## follow the running container's logs
	docker logs -f $(IMAGE)

.PHONY: help black black-check pylint mypy shellcheck unit unit-update-golden integration static static-check clean-cache clean-venv build start stop logs
