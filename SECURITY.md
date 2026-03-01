# Security Policy

## Supported Versions

Only the latest minor release line is actively supported with security fixes.

## Reporting A Vulnerability

Please do not open public issues for security vulnerabilities.

Report privately via GitHub Security Advisories for this repository. Include:

- affected version
- reproduction steps
- impact assessment
- suggested remediation (if available)

We aim to acknowledge reports within 72 hours and provide status updates until
resolution.

## Secrets Handling

- Never commit API keys or tokens to the repository.
- Use `.env` for local development and keep it untracked.
- CI includes secret scanning and will fail on detected leaks.
