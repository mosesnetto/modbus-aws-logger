# Contributing

## Before opening a change

1. Create or use the project virtual environment.
2. Copy `.env.example` to `.env` only when local runtime testing is needed.
3. Never add `.env`, certificates, private keys, logs, or production data.
4. Run the checks below.

```powershell
python -m compileall -q .
python -m unittest discover -s tests -v
python -m pip check
```

## Change guidelines

- Keep configuration and secrets outside the repository.
- Prefer small, testable functions.
- Add or update tests for behavior changes.
- Do not add live infrastructure identifiers to documentation or examples.
- Keep retry behavior bounded and observable.
- Do not claim performance or production readiness without measurements.

## Commit safety

The repository uses `.githooks/pre-commit`. It blocks common certificate, key,
and environment files from being staged. Do not bypass it without reviewing the
contents of every staged file.

## Security reports

Do not open a public issue for a suspected vulnerability. Use the repository's
private security-reporting process and rotate exposed credentials immediately.
