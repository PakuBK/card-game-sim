# card-game-sim

Minimal “first state” scaffold:

- Frontend: Vite+ TypeScript app
- Backend: FastAPI with dummy endpoints
- Dev wiring: Vite dev proxy forwards `/api/*` → `http://127.0.0.1:8000`

## Run locally

### 1) Backend (FastAPI)

```powershell
C:/Users/paulk/AppData/Local/Microsoft/WindowsApps/python3.13.exe -m venv backend/.venv
backend/.venv/Scripts/python -m pip install -r backend/requirements.txt
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
