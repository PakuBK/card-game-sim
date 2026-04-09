# Bazaar Combat Simulation Project Plan

## Purpose

Build a data-driven combat sandbox inspired by _The Bazaar_. The project is not a full game implementation. It is a theory-crafting tool where users define items, boards, and combat parameters as data, then run deterministic simulations to study outcomes and compare builds.

## Execution Snapshot

- Current active phase: Phase 2 Core Engine
- Detailed phase tracker: `docs/phase2_execution_plan.md`
- Quick status:
  - Phase 1 Contract and Scope: complete
  - Phase 2 Core Engine: in progress
  - Phase 3 to Phase 5: not started

## Current State

The repository currently contains the initial application scaffold:

- A Vite+ React frontend shell
- A FastAPI backend shell with dummy endpoints
- Generated OpenAPI TypeScript bindings wired into the frontend
- Local dev wiring for running frontend and backend together

This is the starting point for the real simulation product. The next stage is to replace placeholder behavior with the actual combat model, editor workflows, and results pipeline.

## Product Direction

The long-term direction is a configurable combat simulator with three core capabilities:

1. Define user-authored items as structured data
2. Assemble boards and player setups visually in the frontend
3. Execute deterministic combat simulations in the backend and return statistics

The system should stay generic. Item behavior is not hardcoded as special cases in the backend. Instead, the engine interprets item definitions, triggers, effects, timers, and status interactions supplied by the frontend.

## Architecture Direction

### Frontend

- React-based configuration workspace for item definitions, boards, and simulation settings
- Visual editing for board layout, item placement, and player setup
- Simulation controls for seed, run count, and duration or stop conditions
- Results views for combat logs, aggregate stats, and distributions
- Validation feedback surfaced from backend schema checks

### Backend

- Python FastAPI service that exposes the simulation API
- Pydantic-backed request and response models
- Importable simulation engine with deterministic execution
- Seeded randomness for reproducible runs
- Batch-friendly simulation entrypoints for repeated runs

### Simulation Model

The engine should follow a discrete-event approach:

- Combat progresses by jumping from one scheduled event to the next
- Item cooldowns use absolute trigger times
- Status effects such as burn and poison schedule their own ticks
- Timer modifiers like slow, haste, freeze, and charge force rescheduling when needed
- Board adjacency matters for target selection and item interaction rules

## Scope

The project scope is combat only. It should model the pieces needed for experimentation and balance testing:

- Player health, shield, regeneration, and status effects
- User-defined items with stats, runtime state, triggers, and effects
- Board layouts with item size and adjacency rules
- Damage, healing, shield generation, burn, poison, and related interactions
- Timer-based item use and status ticking
- Single-fight debug runs and batch statistical runs

## Data and API Direction

The backend should define the source-of-truth contracts and generate frontend types from them.

Likely core models include:

- `ItemDefinition`
- `BoardConfig`
- `PlayerConfig`
- `SimulationRequest`
- `SimulationResult`

The API should stay compact and purpose-built for the simulator, with endpoints for health checks, catalog or schema discovery, and simulation execution.

## Metrics and Outputs

The simulator should return outputs that help users understand both single runs and repeated batches. Useful outputs include:

- Win or loss outcome
- Fight duration
- Final health and shield values
- Damage, healing, and status effect totals
- Proc and trigger counts
- Average, median, and percentile summaries across batch runs

## Implementation Phases

### Phase 1: Contract and Scope

- Finalize the simulation primitives and supported status effects
- Define the backend request and response models
- Establish the JSON shape for user-defined items and boards

### Phase 2: Core Engine

- Implement the deterministic combat loop in Python
- Add the event queue, timers, status ticks, and adjacency rules
- Support a minimal but extensible item execution model

### Phase 3: API and Frontend Integration

- Replace dummy endpoints with real simulation routes
- Generate frontend types from OpenAPI
- Build the editor UI for item and board configuration

### Phase 4: Debugging and Analysis UX

- Add single-run inspection views and combat logs
- Add batch run statistics and result comparisons
- Improve validation and error reporting for malformed configurations

### Phase 5: Scale and Packaging

- Add regression tests for determinism and core mechanics
- Optimize for repeated simulations and larger item sets
- Package the app for straightforward local and VPS deployment

## Quality Goals

- Deterministic results for the same seed and input
- Data-driven item behavior without backend special casing
- Clear validation errors for invalid configs
- Fast enough execution for repeated simulations
- Small, understandable initial scope that can expand safely

## Notes

- The project spec is the source of truth for the combat model and design constraints
- The plan should stay broader than the spec and describe the project direction, not every mechanic in implementation detail
- The immediate goal is to turn the current scaffold into a usable simulator foundation, then expand the engine and editor incrementally
