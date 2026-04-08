# card-game-sim

Data-driven combat sandbox inspired by _The Bazaar_. The project is focused on defining items, boards, and combat rules as data, then running deterministic simulations to compare builds and study outcomes.

## What’s In The Repo

- React frontend for configuring builds and reviewing results
- FastAPI backend for deterministic combat simulation
- OpenAPI-generated TypeScript types for shared contracts
- Local dev wiring that runs the frontend and backend together

## Run Locally

### Full stack

```powershell
vp run dev:full
```

This starts the FastAPI backend and the Vite frontend together.

### Backend

```powershell
C:/Users/paulk/AppData/Local/Microsoft/WindowsApps/python3.13.exe -m venv backend/.venv
backend/.venv/Scripts/python -m pip install -r backend/requirements.txt
backend/.venv/Scripts/python backend/run_dev.py
```

`backend/run_dev.py` starts Uvicorn with auto-reload on `127.0.0.1:8000`.

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

### Frontend

```powershell
vp install
vp dev
```

Open the app at the URL printed by `vp dev`.

## Current API Surface

The backend is still a scaffold, so the API surface is intentionally small while the combat engine is built out.

- `GET /api/health`
- `GET /api/cards`
- `POST /api/echo`

## Shared Types

Frontend API types are generated from the FastAPI OpenAPI schema.

1. Start the backend, or run the full stack.
2. Generate types with:

```powershell
vp run gen:api
```

This writes the generated types to `src/api/generated/openapi.ts`.

If formatting changes are needed after regeneration, run:

```powershell
vp fmt src/api/generated/openapi.ts --write
```

Or format everything with:

```powershell
vp check --fix
```

## Direction

The next major milestone is replacing the placeholder API and UI with the real combat configuration and simulation workflow described in `docs/project_spec.md`.
