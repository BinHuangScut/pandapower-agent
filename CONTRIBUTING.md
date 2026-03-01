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
ruff check src tests
pytest -q
python -m build
twine check dist/*
agent --help
agent doctor --format json
```

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
