# Deploy Expense Tracker on Railway (Docker)

This guide deploys the app as 3 Railway services:
- `Postgres`
- `backend` (FastAPI)
- `frontend` (Vite static build via Caddy)

## 1. Pre-check before Railway

1. Confirm these files exist:
- `backend/Dockerfile`
- `frontend/Dockerfile`
- `frontend/Caddyfile`

2. Push latest code to GitHub:
```bash
git add .
git commit -m "Add Railway deployment config"
git push
```

## 2. Create Railway project

1. Go to Railway and create a new project from your GitHub repo.
2. Add a `Postgres` service from Railway templates.
3. Add a new service for backend:
- Source: same GitHub repo
- Root Directory: `backend`
- Railway will detect `backend/Dockerfile`
4. Add a new service for frontend:
- Source: same GitHub repo
- Root Directory: `frontend`
- Railway will detect `frontend/Dockerfile`

## 3. Configure backend environment variables

In Railway backend service, set:

```env
APP_NAME=Expense Tracker API
APP_ENV=prod
SECRET_KEY=<very-long-random-secret>
APP_ENCRYPTION_KEY=
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=10080
DATABASE_URL=postgresql+asyncpg://${{Postgres.PGUSER}}:${{Postgres.PGPASSWORD}}@${{Postgres.PGHOST}}:${{Postgres.PGPORT}}/${{Postgres.PGDATABASE}}
CORS_ALLOW_ORIGINS=https://<your-frontend-domain>

LLM_PROVIDER=openai
LLM_MODEL=gpt-5.1
LLM_DEFAULT_CURRENCY=INR
LLM_TIMEZONE=Asia/Kolkata
OPENAI_API_KEY=<your-openai-api-key>
OPENAI_MODEL=gpt-5.1
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.0-flash
```

Notes:
- Replace `<your-frontend-domain>` after frontend public domain is generated.
- Keep `OPENAI_API_KEY` only on backend service (never in frontend).

## 4. Configure frontend environment variable

In Railway frontend service, set:

```env
VITE_API_BASE_URL=https://<your-backend-domain>
```

Important:
- This is a build-time variable for Vite.
- If you change it, redeploy frontend service.

## 5. Generate public domains

1. Open backend service -> `Settings` -> `Networking` -> `Public Networking` -> `Generate Domain`.
2. Do the same for frontend service.
3. Update:
- Backend `CORS_ALLOW_ORIGINS` with frontend URL.
- Frontend `VITE_API_BASE_URL` with backend URL.
4. Redeploy backend and frontend.

## 6. Health and smoke test

1. Test backend health:
```bash
curl https://<your-backend-domain>/health
```
Expected:
```json
{"status":"ok"}
```

2. Open frontend URL and test:
- Register a user
- Login
- Log an expense
- Confirm draft expense
- Open dashboard

## 7. Common issues and fixes

1. `401 Unauthorized` on protected APIs:
- Ensure request has `Authorization: Bearer <token>`.
- Login again and retry.

2. CORS error in browser:
- Backend `CORS_ALLOW_ORIGINS` must exactly match frontend domain.
- Redeploy backend after changing CORS.

3. Frontend still calls old API URL:
- Update `VITE_API_BASE_URL`.
- Redeploy frontend (build-time env).

4. Backend cannot connect to DB:
- Verify `DATABASE_URL` uses Railway Postgres vars exactly.
- Check Postgres service is running.

5. LLM call fails:
- Confirm `LLM_PROVIDER=openai`
- Confirm `OPENAI_API_KEY` is set in backend service
- Confirm model name is valid for your key

## 8. Minimal security checklist

1. Use a strong `SECRET_KEY` (32+ chars).
2. Do not commit `.env` files with real keys.
3. Keep API keys only in Railway service variables.
4. Rotate OpenAI key if accidentally exposed.

## 9. Deployment order (recommended)

1. Deploy `Postgres`
2. Deploy `backend`
3. Set frontend `VITE_API_BASE_URL`
4. Deploy `frontend`
5. Run smoke tests
