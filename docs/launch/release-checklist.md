# Release Checklist (v0.1.0)

## Security and compliance

- [ ] Rotate/revoke any API keys that were ever exposed in local or historical files.
- [ ] Confirm `.env` is not tracked and `.env.example` contains placeholders only.
- [ ] Ensure CI secret scan job passes.

## Repository readiness

- [ ] Governance files exist: `LICENSE`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`.
- [ ] Community templates exist: issue templates, PR template, discussion templates.
- [ ] README quickstart commands are copy-paste validated.

## Build and validation

```bash
pip install -e .[dev]
ruff check src tests
pytest -q
agent --help
agent --version
agent doctor --format json
python -m build
twine check dist/*
```

## TestPyPI trusted publisher setup

- [ ] Create project on TestPyPI (`pandapower-agent`) if not already created.
- [ ] Configure trusted publisher for owner `BinHuangScut`, repo `pandapower-agent`, workflow `publish-testpypi.yml`, environment `testpypi`.
- [ ] Create GitHub Environment `testpypi` for this repository.

## Test package publish contract

- [ ] `publish-testpypi.yml` triggers on `main` push with paths: `src/**`, `pyproject.toml`, `MANIFEST.in`, `README.md`, `LICENSE`.
- [ ] `workflow_dispatch` is enabled for manual backfill.
- [ ] CI mutates package version only in runner workspace as `<base>.dev<github.run_number>` (example: `0.1.0.dev123`).
- [ ] Publish target is TestPyPI only (`https://test.pypi.org/legacy/`) via OIDC trusted publisher.
- [ ] Post-publish smoke installs exact version from TestPyPI and runs `agent --version`, `agent --help`, `agent networks --max 3 --format json`.

## Production PyPI status

- [ ] Production PyPI publishing is paused in `release.yml`.
- [ ] Tag release still creates GitHub Release artifacts only.

## GitHub release

- [ ] Ensure `docs/assets/quick-demo.gif` is present and referenced in README.
- [ ] Publish tag `v0.1.0`.
- [ ] Confirm `release.yml` creates GitHub Release and uploads artifacts.

## Launch distribution

- [ ] Post launch thread in order: GitHub Release -> X/LinkedIn -> Reddit -> Chinese communities.
- [ ] Use unified CTA: `Star + Try + Share a case`.
- [ ] Start first-week triage cadence.
