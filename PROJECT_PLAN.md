# Card Build Simulator POC Plan

## Goal

Build a proof-of-concept web app where users create a card build in a React frontend, submit it to a Python backend, and run a deterministic simulation that returns aggregated stats. The backend should preserve the legacy simulator architecture: ECS-style entities/components, transactional actions, status effects, board adjacency, and an event bus for reactive effects.

## Recommended Stack

- Frontend: React
- Backend: Python with FastAPI
- Validation: Pydantic on the backend, generated TypeScript types on the frontend
- Deployment: Docker on a single VPS

## Architecture Outline

### Frontend

- Single-screen React app
- Card/item catalog panel
- Build editor for selected cards/items and counts
- Simulation controls for duration, iterations, and seed
- Results panel for aggregated stats and distributions
- Display validation errors returned by the API

### Backend

- FastAPI HTTP API
- Importable simulation package in Python
- Deterministic simulation loop using a virtual clock
- Seeded RNG for reproducible runs
- Synchronous `/api/simulate` endpoint for the POC

### Core Simulation Model

Preserve the legacy design instead of flattening it into generic game logic:

- Entity/component composition instead of hard-coded class hierarchies
- Actions with conditions, costs, and effects
- Centralized status effect handling
- Board adjacency for item interactions
- Event bus or observer pattern for triggered effects
- Deterministic tick or event-queue based execution

## POC Scope

Start with the smallest useful port of the old simulator:

- Player entities
- Items/cards
- Cooldowns and charging
- Ammo or resource gating
- Status effects like burn, poison, regeneration, haste, slow, freeze
- Board adjacency
- Combat loop over a fixed time interval

## Suggested Stats

Return a compact summary such as:

- Total damage or score
- Damage over time breakdown
- Proc counts
- Shield absorbed
- HP remaining
- Time-to-kill or failure/idle rate
- Average, p50, and p95 values across runs

## Backend API

### Endpoints

- `GET /api/health`
- `GET /api/cards` or `GET /api/items`
- `POST /api/simulate`

### Request Guardrails

- Clamp duration and iteration count
- Reject invalid configs with clear errors
- Limit payload size
- Add request timeout protection

## Data Contracts

Define backend models first and generate frontend types from OpenAPI:

- `BuildConfig`
- `EntityConfig` or `ItemConfig`
- `SimulationParams`
- `SimulationResult`

## Testing

Focus tests where the architecture is fragile:

- Determinism: same seed and config produce identical results
- Legacy behavior fixtures: shield, poison, burn, freeze, cooldown, adjacency, triggered effects
- API validation tests for bad payloads

## Packaging and Deployment

Use a single Docker container for the POC if possible:

- FastAPI serves the built React assets
- FastAPI also serves `/api/*`
- Add `docker-compose.yml` for local and VPS deployment
- Put HTTPS in front with Caddy or Nginx if needed

## Implementation Order

1. Define the exact simulation scope and stats
2. Port the legacy simulation model into Python modules
3. Add FastAPI models and endpoints
4. Build the React frontend around the API
5. Add tests for determinism and key mechanics
6. Package with Docker
7. Deploy to the VPS

## Notes

- The legacy repository is on the `master` branch
- The old simulator is a good source of architecture, behavior, and data model ideas
- Keep the first version small and data-driven so the editor and simulation stay manageable
