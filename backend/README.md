# Backend (FastAPI)

## Setup

From the repo root:

```bash
python -m venv backend/.venv
backend/.venv/Scripts/python -m pip install -r backend/requirements.txt
```

## Run (dev)

```bash
backend/.venv/Scripts/python -m uvicorn backend.app.main:app --reload --port 8000
```

## Endpoints

- `GET /api/health`
- `GET /api/cards` (dummy data)
- `POST /api/echo`
