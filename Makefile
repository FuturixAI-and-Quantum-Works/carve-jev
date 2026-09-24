.PHONY: install serve benchmark lint format test build check

install:
	python -m pip install -e ".[dev]"

serve:
	bash scripts/quickstart.sh

benchmark:
	bash scripts/run_full_benchmark.sh

lint:
	ruff check .
	ruff format --check .

format:
	ruff check --fix .
	ruff format .

test:
	pytest -q

build:
	python -m build

check: lint test build
