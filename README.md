# Expense Tracker App

An open-source household expense tracker with:
- natural-language expense capture
- voice transcription for expense logging
- shared household ledger and access controls
- analytics and AI-assisted spending insights

The repository contains a FastAPI backend and a React (Vite) frontend.

## Tech Stack
- Backend: FastAPI, SQLModel, PostgreSQL/SQLite, uv
- Frontend: React 18, Vite
- AI integrations: OpenAI, Cerebras, Gemini, Groq Whisper (configurable)

## Repository Structure
- `backend/` API, models, services, tests
- `frontend/` web client
- `DEPLOY_RAILWAY.md` deployment guide
- `.env.example` example environment variables

## Quick Start (Local)

Prerequisites:
- Python 3.11+
- Node.js 18+
- `uv` installed

1. Clone and enter the repository.
```bash
git clone https://github.com/<your-username>/<your-repo>.git
cd <your-repo>
```

2. Configure backend environment.
```bash
cp .env.example .env
```

3. Run backend.
```bash
cd backend
uv venv
uv sync --extra dev
uv run uvicorn app.main:app --reload
```

4. Run frontend (new terminal).
```bash
cd frontend
npm install
npm run dev
```

Backend defaults to `http://127.0.0.1:8000`, frontend defaults to `http://localhost:5173`.

## Test Commands

Backend:
```bash
cd backend
uv run pytest -q
```

Frontend build check:
```bash
cd frontend
npm run build
```

## Deployment

Use Railway deployment instructions in `DEPLOY_RAILWAY.md`.

## Contributing

Please read `CONTRIBUTING.md` before opening pull requests.

## Security

Please read `SECURITY.md` for vulnerability reporting guidance.

## License

MIT License. See `LICENSE`.
