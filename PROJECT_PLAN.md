# Bazaar Combat Simulation Project Plan

## Purpose

Build a data-driven combat sandbox inspired by _The Bazaar_. The project is not a full game implementation. It is a theory-crafting tool where users define items, boards, and combat parameters as data, then run deterministic simulations to study outcomes and compare builds.

## Execution Snapshot

- Current active phase: Phase 4 Debugging and Analysis UX (mid)
- Quick status:
  - Phase 1 Contract and Scope: complete
  - Phase 2 Core Engine: complete
  - Phase 2.5 Item Status Effects Extension: complete
  - Phase 3 API and Frontend Integration: complete
  - Phase 4 Debugging and Analysis UX: in progress
  - Phase 5 Scale and Packaging: not started

## Current State

The repository now contains a working deterministic combat simulation foundation and practical debug tooling:

- FastAPI simulation endpoints and schema endpoint (`/api/health`, `/api/simulation/schema`, `/api/simulate`)
- Discrete-event simulation engine with deterministic ordering and seeded runs
- Player status effects implemented: burn, poison, regeneration
- Item timer modifiers implemented: slow, haste, freeze, charge, flight
- Expanded target scope for item effects (opponent/self item selectors, left-most/right-most, size-based, random)
- Structured metrics in simulation output (player and item level damage/event/status summaries)
- Combat log support with `combat_log_limit` and truncation metadata
- Modifier timer trace emitted per run for timer debugging
- OpenAPI-generated TypeScript contracts wired into frontend API calls
- Typed frontend HTTP error handling with parsed API error bodies
- Frontend debug surfaces:
  - `src/pages/debug/DebugPage.tsx` for schema viewing, preset payloads, per-run logs, and modifier traces
  - `src/pages/simulator/SimulatorPage.tsx` for visual build authoring, matchup execution, and build comparison
- Simulator workspace authoring features:
  - local workspace persistence for builds/settings/comparison state
  - build library CRUD for both sides (new/select/duplicate/delete)
  - editable item definitions, effects, placements, statuses, and player stats
  - board preview with click-to-place and click-to-move interactions
  - local workspace validation before run/compare execution
- Inline API error guidance:
  - backend detail locations mapped to editor sections (stats, board, placements, items, statuses, settings)
  - surfaced for both current matchup and build comparison failure paths
- Damage comparison chart:
  - side-by-side median + overlay run curves for build comparison results
- Backend deterministic and mechanics tests in `backend/tests`

The next stage is to move from debug-oriented JSON workflows to a dedicated visual authoring experience while preserving deterministic contracts and traceability.

Update: a dedicated visual authoring workspace now exists in the simulator page. The next stage is to harden that UX and expand analysis depth.

## Product Direction

The long-term direction is a configurable combat simulator with three core capabilities:

1. Define user-authored items as structured data
2. Assemble boards and player setups visually in the frontend
3. Execute deterministic combat simulations in the backend and return statistics

The system should stay generic. Item behavior is not hardcoded as special cases in the backend. Instead, the engine interprets item definitions, triggers, effects, timers, and status interactions supplied by the frontend.

## Gap Analysis Against Spec Vision

What is aligned today:

- Deterministic, event-driven backend execution model
- Data-driven item and board payload contracts
- Core status and timer-modifier mechanics
- Batch and single-run style outputs via one simulation endpoint
- Stable metrics foundation for future analysis features
- Visual authoring and comparison workflow on the simulator page
- Section-level API error guidance mapped from backend validation details

What is still missing to meet the intended UX:

- Broader distribution analysis (beyond current median + single overlay comparison)
- More advanced board interactions (drag/drop and richer placement ergonomics)
- Expanded export and filtering workflows for logs and traces
- Expanded automated regression coverage and packaging hardening

## Architecture Direction

### Frontend

- Keep TanStack Router + React Query as the data/navigation base
- Continue evolving the simulator visual builders:
  - Item definition editor (implemented)
  - Board placement editor with size and slot constraints (implemented, with click-to-place/move)
  - Player setup editor for stats and initial statuses (implemented)
- Retain advanced debug surfaces (`DebugPage`) for engine diagnostics
- Expand comparative analysis views for multi-run outcomes
- Continue improving inline validation and API guidance ergonomics

### Backend

- Python FastAPI service that exposes the simulation API
- Pydantic-backed request and response models
- Importable simulation engine with deterministic execution
- Seeded randomness for reproducible runs
- Batch-friendly simulation entrypoints for repeated runs
- Continue additive contract evolution so frontend types remain stable

### Simulation Model

The engine should follow a discrete-event approach:

- Combat progresses by jumping from one scheduled event to the next
- Item cooldowns use absolute trigger times
- Status effects such as burn and poison schedule their own ticks
- Timer modifiers like slow, haste, freeze, and charge force rescheduling when needed
- Board adjacency matters for target selection and item interaction rules

Current note: this model is implemented and active in production code paths.

## Scope

The project scope is combat only. It should model the pieces needed for experimentation and balance testing:

- Player health, shield, regeneration, and status effects
- User-defined items with stats, runtime state, triggers, and effects
- Board layouts with item size and adjacency rules
- Damage, healing, shield generation, burn, poison, and related interactions
- Timer-based item use and status ticking
- Single-fight debug runs and batch statistical runs

Near-term scope control:

- Keep expanding through additive effects/targets rather than bespoke item logic
- Avoid introducing non-deterministic behavior without explicit seeded control

## Data and API Direction

The backend should define the source-of-truth contracts and generate frontend types from them.

Current core models include:

- `ItemDefinition`
- `BoardConfig`
- `PlayerConfig`
- `SimulationRequest`
- `SimulationResponse`

Current response shape already includes:

- `runs[]` with per-run winner/duration/stop reason/player state
- `metrics` with per-player and per-item breakdowns
- `combat_log` and truncation metadata
- `modifier_timer_trace` for timer debugging
- `summary` with win rates and duration percentiles

The API should stay compact and purpose-built for the simulator, with endpoints for health checks, catalog or schema discovery, and simulation execution.

## Metrics and Outputs

The simulator should return outputs that help users understand both single runs and repeated batches. Useful outputs include:

- Win or loss outcome
- Fight duration
- Final health and shield values
- Damage, healing, and status effect totals
- Proc and trigger counts
- Average, median, and percentile summaries across batch runs

Current implementation status:

- Baseline metrics and summaries are implemented and returned
- Metrics keys are stable enough for frontend table and chart integration
- Remaining work is primarily presentation and comparative analytics UX

## Implementation Phases

### Phase 1: Contract and Scope

- Finalize the simulation primitives and supported status effects
- Define the backend request and response models
- Establish the JSON shape for user-defined items and boards

Status: complete.

### Phase 2: Core Engine

- Implement the deterministic combat loop in Python
- Add the event queue, timers, status ticks, and adjacency rules
- Support a minimal but extensible item execution model

Status: complete.

### Phase 2.5: Extending the Core Engine with time based effects

- Extend status effects to include item status effects like haste, freeze, slow, and flying.
- Create test coverage for said effects.

Status: complete.

### Phase 3: API and Frontend Integration

- Replace dummy endpoints with real simulation routes
- Generate frontend types from OpenAPI
- Build the editor UI for item and board configuration

Status: complete.

- Done: real API routes, typed frontend API client, generated OpenAPI contracts, integrated debug pages, and visual simulator authoring workflows for items/boards/players.

### Phase 4: Debugging and Analysis UX

- Add single-run inspection views and combat logs
- Add batch run statistics and result comparisons
- Improve validation and error reporting for malformed configurations

Status: in progress.

- Done:
  - single-run inspection, combat logs, modifier timer traces, and per-run metric tables
  - visual simulator workspace with build authoring and comparison execution
  - side-by-side build comparison with median + overlay damage curves
  - inline API error guidance mapped to concrete editor sections
- Next:
  - richer aggregate/distribution analytics (percentile bands/histograms)
  - additional UX polish for board authoring interactions and discoverability
  - export/filter improvements for logs and traces

### Phase 5: Scale and Packaging

- Add regression tests for determinism and core mechanics
- Optimize for repeated simulations and larger item sets
- Package the app for straightforward local and VPS deployment

Status: not started.

Planned entry criteria:

- Frontend authoring UX is usable without manual JSON editing.
- Core analysis workflows are stable enough to benchmark and optimize.

## Quality Goals

- Deterministic results for the same seed and input
- Data-driven item behavior without backend special casing
- Clear validation errors for invalid configs
- Fast enough execution for repeated simulations
- Small, understandable initial scope that can expand safely

Current quality signal:

- `vp check` is clean.
- Core backend behavior has targeted tests for deterministic outcomes and status/timer interactions.
- Additional frontend interaction coverage and contract-regression tests are still needed as UX complexity grows.

## Next 30-60 Day Priorities

1. Harden simulator authoring UX

- Improve board interaction affordances (selection cues, move/cancel behavior, keyboard support)
- Add regression coverage for placement helpers and workspace transformations
- Ensure error guidance remains stable as backend contract details evolve

2. Improve analysis UX

- Expand comparison views with richer distribution summaries
- Add aggregated distributions/charts from batch results
- Add better filtering/export for combat logs and timer traces

3. Strengthen validation and regression confidence

- Expand frontend validation aligned to backend schema constraints
- Add contract and determinism regression tests around high-risk mechanics
- Add frontend tests for API error mapping and section-level surfacing

4. Prepare for scale phase entry

- Profile event-loop hotspots with larger synthetic batches
- Define deployment target and packaging checklist

## Notes

- The project spec is the source of truth for the combat model and design constraints
- The plan should stay broader than the spec and describe delivery priorities and status
- The immediate goal is to complete visual authoring and analysis workflows on top of the already functional deterministic engine
