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

## PyPI setup

- [ ] Create project on PyPI (`pandapower-agent`) if not already created.
- [ ] Configure trusted publisher for this GitHub repository and `release.yml` workflow.
- [ ] Tag release in SemVer format: `v0.1.0`.

## GitHub release

- [ ] Ensure `docs/assets/quick-demo.gif` is present and referenced in README.
- [ ] Publish tag `v0.1.0`.
- [ ] Confirm `release.yml` creates GitHub Release and uploads artifacts.
- [ ] Confirm PyPI publish job succeeds.

## Launch distribution

- [ ] Post launch thread in order: GitHub Release -> X/LinkedIn -> Reddit -> Chinese communities.
- [ ] Use unified CTA: `Star + Try + Share a case`.
- [ ] Start first-week triage cadence.
