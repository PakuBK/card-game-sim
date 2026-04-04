# Backend (FastAPI)

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

`backend/run_dev.py` is a tiny launcher that calls Uvicorn for
`backend.app.main:app` with `reload=True`.

Optional host/port overrides:

```bash
BACKEND_HOST=127.0.0.1 BACKEND_PORT=8001 backend/.venv/Scripts/python backend/run_dev.py
```

Equivalent direct Uvicorn command:

```bash
backend/.venv/Scripts/python -m uvicorn backend.app.main:app --reload --port 8000
```

## API docs

FastAPI auto-generates OpenAPI docs from your routes and Pydantic models.

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

## Endpoints

- `GET /api/health`
- `GET /api/cards` (dummy data)
- `POST /api/echo`
