# Contributing to 0rb1t

## Development setup

```bash
git clone <repo-url>
cd 0rb1t
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .[dev]
```

## Running tests

```bash
PYTHONPATH=src pytest -q
```

## Guidelines

- Keep changes focused and avoid destructive rewrites.
- Preserve OpenCode compatibility unless intentionally changing adapter behavior.
- Add tests for config, command dispatch, and plugin behavior when changing core systems.
- Prefer clear error messages over silent failure.
- Update docs when user-facing behavior changes.

## Pull requests

- Describe the problem and the approach.
- Note trade-offs and migration impact.
- Include test/validation results.
