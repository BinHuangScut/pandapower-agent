.PHONY: lint test build check clean

lint:
	ruff check src tests

test:
	pytest -q

build:
	python -m build

twine-check:
	twine check dist/*

check: lint test build twine-check
	pre-commit run --all-files

clean:
	rm -rf dist build .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage
	find . -type d -name '__pycache__' -prune -exec rm -rf {} +
	find . -type d -name '*.egg-info' -prune -exec rm -rf {} +
