# card-game-sim

Minimal “first state” scaffold:

- Frontend: Vite+ TypeScript app
- Backend: FastAPI with dummy endpoints
- Dev wiring: Vite dev proxy forwards `/api/*` → `http://127.0.0.1:8000`

## Run locally

### One command for both processes

```powershell
vp run dev:full
```

This starts the FastAPI backend and the Vite frontend together.

### 1) Backend (FastAPI)

```powershell
C:/Users/paulk/AppData/Local/Microsoft/WindowsApps/python3.13.exe -m venv backend/.venv
backend/.venv/Scripts/python -m pip install -r backend/requirements.txt
backend/.venv/Scripts/python backend/run_dev.py
```

This launcher script starts Uvicorn with auto-reload on `127.0.0.1:8000`.
Optional overrides:

```powershell
$env:BACKEND_HOST="127.0.0.1"
$env:BACKEND_PORT="8001"
backend/.venv/Scripts/python backend/run_dev.py
```

Equivalent direct Uvicorn command:

```powershell
backend/.venv/Scripts/python -m uvicorn backend.app.main:app --reload --port 8000
```

Open the API docs at `http://127.0.0.1:8000/docs`.

### 2) Frontend (Vite+)

```powershell
vp install
vp dev
```

Open the app at the URL printed by `vp dev` (typically `http://localhost:5173`).

## Dummy endpoints

- `GET /api/health`
- `GET /api/cards`
- `POST /api/echo`

## Frontend API types (OpenAPI)

TypeScript types are generated from the FastAPI OpenAPI schema.

1. Start the backend (or run full stack):

```powershell
vp run dev:backend
```

2. Generate types:

```powershell
vp run gen:api
```

This writes the generated types to `src/api/generated/openapi.ts`.

Note: a Vite+ git `pre-commit` hook attempts to run `vp run gen:api` automatically and stage the updated generated file. If generation fails, it will warn and continue the commit.

If `vp check` reports formatting issues after regeneration, run:

```powershell
vp fmt src/api/generated/openapi.ts --write
```

Or (formats everything):

```powershell
vp check --fix
```

## Frontend validation (Zod)

The React UI uses Zod for client-side validation of user input (example: Echo message).
