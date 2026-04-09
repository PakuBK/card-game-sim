# Backend (FastAPI)

The backend is the execution layer for the combat simulator. It currently provides the FastAPI scaffold that will grow into the deterministic simulation API described in `docs/project_spec.md`.

## Setup

From the repo root:

```bash
python -m venv backend/.venv
backend/.venv/Scripts/python -m pip install -r backend/requirements.txt
```

## Run (dev)

```bash
backend/.venv/Scripts/python backend/run_dev.py
```

To start both the backend and frontend together from the repo root, run:

```bash
vp run dev:full
```

`backend/run_dev.py` launches Uvicorn for `backend.app.main:app` with reload enabled.

Optional host and port overrides:

```bash
BACKEND_HOST=127.0.0.1 BACKEND_PORT=8001 backend/.venv/Scripts/python backend/run_dev.py
```

Equivalent direct Uvicorn command:

```bash
backend/.venv/Scripts/python -m uvicorn backend.app.main:app --reload --port 8000
```

## API docs

FastAPI auto-generates OpenAPI docs from the current routes and Pydantic models.

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

## Debug Scenarios

For targeted item-status debugging, run deterministic scenarios with timeline output:

```bash
vp run debug:item-status
```

Run a single scenario:

```bash
vp run debug:item-status -- --scenario slow_basic
```

Show full combat log entries:

```bash
vp run debug:item-status -- --scenario freeze_basic --full-log --event-limit 200
```

Show internal timer reschedule math (old/new timing, remaining cooldown, charge):

```bash
vp run debug:item-status --scenario freeze_basic --verbose-timers
```

Available scenarios:

- `slow_basic`
- `charge_basic`
- `freeze_basic`
- `flight_halving`

## Current Endpoints

The API now includes the Phase 1 contract and scope endpoints.

- `GET /api/health`
- `GET /api/simulation/schema`
- `POST /api/simulate`

## Direction

The backend will become the deterministic combat engine for user-defined items, board layouts, and simulation results. It should stay data-driven and avoid hardcoding item behavior directly into endpoint logic.
