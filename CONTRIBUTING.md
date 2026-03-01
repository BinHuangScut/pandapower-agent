# Contributing

Thanks for contributing to `pandapower-agent`.

## Development Setup

```bash
conda env create -f environment.yml
conda activate pandapower-agent
pip install -e .[dev]
```

## Quality Gates

Run before opening a pull request:

```bash
pre-commit run --all-files
ruff check src tests
pytest -q
python -m build
twine check dist/*
agent --help
agent doctor --format json
```

## File Placement Rules

- CLI parsing/dispatch logic belongs in `src/pandapower_agent/cli/`.
- LLM runtime behavior belongs in `src/pandapower_agent/agent/`.
- Tool handler logic belongs in `src/pandapower_agent/power/handlers/`.
- Tool registration and execution lifecycle belong in `src/pandapower_agent/power/registry.py` and `src/pandapower_agent/power/executor.py`.
- Schemas and typed payloads belong in `src/pandapower_agent/schema/`.
- Tests must mirror runtime modules under `tests/cli`, `tests/agent`, `tests/power`, and `tests/schema`.

## Root Directory Policy

- Do not add product or tutorial markdown files directly under repository root.
- Place all long-form docs under `docs/` (`docs/user`, `docs/tech`, `docs/launch`, `docs/archive`).
- Keep root focused on project metadata and entry points (`README.md`, `pyproject.toml`, `CONTRIBUTING.md`, etc.).

## Commit And PR Scope

- Keep PRs focused on one change set.
- Add or update tests for behavior changes.
- Update docs for user-facing command or output changes.
- Do not include secrets in any file, screenshot, or logs.

## Pull Request Checklist

- [ ] Tests pass locally.
- [ ] Lint passes locally.
- [ ] Backward compatibility considered for CLI behavior.
- [ ] README/docs updated when needed.
- [ ] CHANGELOG entry added for notable changes.

## Reporting Bugs

Use the bug report template and include:

- CLI command used
- expected behavior
- actual behavior
- minimal reproducible case
- versions (`python --version`, `agent --version`)

## First-Time Contributions

Look for issues labeled `good first issue` and `help wanted`.
