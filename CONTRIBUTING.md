# Contributing Guide

Thanks for contributing.

## Development Setup

1. Fork the repository and clone your fork.
2. Create a feature branch from `main`.
3. Install dependencies:
   - Backend:
     ```bash
     cd backend
     uv venv
     uv sync --extra dev
     ```
   - Frontend:
     ```bash
     cd frontend
     npm install
     ```

## Before Opening a Pull Request

Run checks locally:

Backend tests:
```bash
cd backend
uv run pytest -q
```

Frontend build:
```bash
cd frontend
npm run build
```

## Pull Request Expectations

- Keep changes focused and scoped.
- Add or update tests for behavior changes.
- Update docs when adding or changing endpoints, env vars, or setup.
- Use clear commit messages.

## Coding Notes

- Do not commit secrets (`.env`, API keys, credentials).
- Follow existing project structure and naming conventions.
- Prefer small, reviewable PRs over large rewrites.

## Reporting Bugs / Requesting Features

- Use GitHub Issues.
- Include reproduction steps, expected behavior, and actual behavior.
