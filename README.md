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

The backend now exposes the Phase 1 contract and simulation endpoints.

- `GET /api/health`
- `GET /api/simulation/schema`
- `POST /api/simulate`

The `/api/simulate` route returns a structured error envelope for:

- Request validation errors (`422`)
- Simulation input/runtime contract errors (`400`)
- Unexpected runtime failures (`500`)

## Metrics Contract

Each simulation run returns structured metrics designed for later visualization and analysis. Metrics are split by player and itemized per board item.

### Example Response Structure

```json
{
  "runs": [
    {
      "run_index": 0,
      "winner_player_id": "player_a",
      "duration_seconds": 5.5,
      "combat_log_total_events": 47,
      "combat_log_truncated": false,
      "combat_log": [
        {
          "event_index": 0,
          "time_seconds": 1.0,
          "event_type": "item_use",
          "source_player_id": "player_a",
          "source_item_instance_id": "a-katana",
          "target_id": "a-katana",
          "state_deltas": [
            {
              "player_id": "player_b",
              "health_delta": -5.0,
              "shield_delta": 0.0,
              "burn_delta": 0.0,
              "poison_delta": 0.0,
              "health_after": 25.0,
              "shield_after": 0.0,
              "burn_after": 0.0,
              "poison_after": 0.0
            }
          ]
        }
      ],
      "metrics": {
        "total_events_processed": 47,
        "player_a": {
          "item_uses": 5,
          "burn_ticks": 3,
          "poison_ticks": 0,
          "regen_ticks": 5,
          "damage_to_opponent": {
            "total": 25.0,
            "direct": 20.0,
            "burn": 5.0,
            "poison": 0.0
          },
          "status_effects_applied": {
            "burn": { "applications": 1, "total_value": 5.0 },
            "poison": { "applications": 0, "total_value": 0.0 }
          },
          "status_effects_received": {
            "burn": { "applications": 0, "total_value": 0.0 },
            "poison": { "applications": 0, "total_value": 0.0 }
          },
          "item_metrics": [
            {
              "item_instance_id": "a-katana",
              "item_definition_id": "katana",
              "owner_player_id": "player_a",
              "damage_done": {
                "total": 25.0,
                "direct": 20.0,
                "burn": 5.0,
                "poison": 0.0
              },
              "events_triggered": {
                "used": 5,
                "damage": 5,
                "apply_burn": 1,
                "burn_tick": 3
              },
              "status_effects_applied": {
                "burn": { "applications": 1, "total_value": 5.0 },
                "poison": { "applications": 0, "total_value": 0.0 }
              },
              "status_effects_received": {}
            }
          ]
        },
        "player_b": {
          "item_uses": 4,
          "burn_ticks": 0,
          "poison_ticks": 0,
          "regen_ticks": 5,
          "damage_to_opponent": {
            "total": 20.0,
            "direct": 20.0,
            "burn": 0.0,
            "poison": 0.0
          },
          "status_effects_applied": {
            "burn": { "applications": 0, "total_value": 0.0 },
            "poison": { "applications": 0, "total_value": 0.0 }
          },
          "status_effects_received": {
            "burn": { "applications": 1, "total_value": 5.0 },
            "poison": { "applications": 0, "total_value": 0.0 }
          },
          "item_metrics": [
            {
              "item_instance_id": "b-katana",
              "item_definition_id": "katana",
              "owner_player_id": "player_b",
              "damage_done": {
                "total": 20.0,
                "direct": 20.0,
                "burn": 0.0,
                "poison": 0.0
              },
              "events_triggered": {
                "used": 4,
                "damage": 4
              },
              "status_effects_applied": {
                "burn": { "applications": 0, "total_value": 0.0 },
                "poison": { "applications": 0, "total_value": 0.0 }
              },
              "status_effects_received": {}
            }
          ]
        }
      }
    }
  ]
}
```

### Key Metric Fields

**Per-Player Metrics:**

- `item_uses`: Count of item activations by the player
- `burn_ticks`, `poison_ticks`, `regen_ticks`: Count of status/regen events affecting the player
- `damage_to_opponent`: Total, direct, burn, and poison damage dealt (split for future visualization)
- `status_effects_applied`: Burn and poison applications initiated by the player (count + total value)
- `status_effects_received`: Burn and poison received by the player (count + total value)
- `item_metrics`: Itemized breakdown by board instance

**Per-Item Metrics:**

- `damage_done`: Total and split damage attributed to this item instance
- `events_triggered`: Dictionary of event counts (e.g., `used`, `damage`, `apply_burn`, `burn_tick`)
- `status_effects_applied`: Status applications originating from this item
- `status_effects_received`: Placeholder for item-level statuses (populated when item status mechanics like slow/haste are added)

**Combat Log Fields:**

- `combat_log`: Ordered event entries for run inspection and regression snapshots
- `combat_log_total_events`: Count of all processed events for the run (before any cap)
- `combat_log_truncated`: Whether returned log entries were capped
- Request option `combat_log_limit`: Optional per-run cap for returned log entries in batch-heavy runs

These metrics are deterministic for identical seeds and payloads, and remain stable across runs to support regression testing and visualization pipelines.

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

## Tests

Run frontend and backend tests together:

```powershell
vp run test:all
```

Run only frontend tests:

```powershell
vp run test:frontend
```

Run only backend tests:

```powershell
vp run test:backend
```

## Direction

The next major milestone is replacing the placeholder API and UI with the real combat configuration and simulation workflow described in `docs/project_spec.md`.
