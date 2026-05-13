# Bazaar Combat Simulation Project Plan

## Purpose

Build a data-driven combat sandbox inspired by _The Bazaar_. The project is not a full game implementation. It is a theory-crafting tool where users define items, boards, and combat parameters as data, then run deterministic simulations to study outcomes and compare builds.

Required scope extension now includes first-class support for:

- Player Skills (static event-driven passives)
- Item Crit mechanics (seeded deterministic crit rolls)
- Item Ammunition mechanics (consume, block-on-empty, reload semantics)

## Execution Snapshot

- Current active phase: Phase 4 Debugging and Analysis UX (mid)
- Quick status:
  - Phase 1 Contract and Scope: complete
  - Phase 2 Core Engine: complete
  - Phase 2.5 Item Status Effects Extension: complete
  - Phase 3 API and Frontend Integration: complete
  - Phase 4 Debugging and Analysis UX: in progress
  - Phase 4.5 Combat Feature Extensions (Skills/Crit/Ammo): not started
  - Phase 5 Scale and Packaging: not started

## Current State

The repository now contains a working deterministic combat simulation foundation and practical debug tooling:

- FastAPI simulation endpoints and schema endpoint (`/api/health`, `/api/simulation/schema`, `/api/simulate`)
- Discrete-event simulation engine with deterministic ordering and seeded runs
- Player status effects implemented: burn, poison, regeneration
- Item timer modifiers implemented: slow, haste, freeze, charge, flight
- Abilities-first item model (trigger + effects); legacy top-level item effects are not supported
- Expanded target scope for item effects (player/item selectors, left-most/right-most, size-based, adjacency, random)
- Multi-target execution for item effects (single/all/random_n)
- Structured metrics in simulation output (player and item level damage/event/status summaries)
- Combat log support with `combat_log_limit` and truncation metadata (includes combat_start at time 0)
- Modifier timer trace emitted per run for timer debugging
- OpenAPI-generated TypeScript contracts wired into frontend API calls
- Typed frontend HTTP error handling with parsed API error bodies
- Frontend debug surfaces:
  - `src/pages/debug/DebugPage.tsx` for schema viewing, preset payloads, per-run logs, and modifier traces
  - `src/pages/simulator/SimulatorPage.tsx` for visual build authoring, matchup execution, and build comparison
- Simulator workspace authoring features:
  - local workspace persistence for builds/settings/comparison state
  - build library CRUD for both sides (new/select/duplicate/delete)
  - editable item definitions, ability effects (timed_use), placements, statuses, and player stats
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

- Skills framework (player-level static passives with per-fight counters and conditional triggers)
- Crit framework (base/runtime crit stats, deterministic seeded crit rolls, crit telemetry)
- Ammunition framework (ammo-gated item uses, reload effects, immediate-use-on-late-reload behavior)
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
- Add skill authoring and skill inspection UX (event conditions, counters, per-fight flags)
- Add item crit and ammo controls in build editor (stats + current runtime previews)
- Add run-result visibility for crit/ammo/skill telemetry

### Backend

- Python FastAPI service that exposes the simulation API
- Pydantic-backed request and response models
- Importable simulation engine with deterministic execution
- Seeded randomness for reproducible runs
- Batch-friendly simulation entrypoints for repeated runs
- Continue additive contract evolution so frontend types remain stable
- Extend runtime model with player skills and skill state machines
- Extend item runtime model with crit and ammo state
- Enforce deterministic crit roll stream based on run seed

### Simulation Model

The engine should follow a discrete-event approach:

- Combat progresses by jumping from one scheduled event to the next
- Item cooldowns use absolute trigger times
- Status effects such as burn and poison schedule their own ticks
- Timer modifiers like slow, haste, freeze, and charge force rescheduling when needed
- Board adjacency matters for target selection and item interaction rules
- Skills are evaluated from the same event stream with deterministic ordering
- Crit rolls are deterministic and seeded per run
- Ammo gating can suppress item-use scheduling until reload conditions are met

Current note: this model is implemented and active in production code paths.

## Scope

The project scope is combat only. It should model the pieces needed for experimentation and balance testing:

- Player health, shield, regeneration, and status effects
- Player skills with per-fight counters/conditions
- User-defined items with stats, runtime state, triggers, and effects
- Crit-aware item uses (base/runtime crit stats + crit multiplier behavior)
- Ammo-aware item uses (consume, empty-state suppression, reload)
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
- `SkillDefinition` (planned)
- `BoardConfig`
- `PlayerConfig`
- `SimulationRequest`
- `SimulationResponse`

Planned contract extensions:

- Item crit fields (for example base/runtime crit chance)
- Optional ammo fields for item definitions/runtime state
- Player skill list in request payload
- Skill trigger/effect descriptors with per-fight limits
- Crit/ammo/skill telemetry sections in run metrics

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
- Crit roll/success rates and crit-attributed effect totals
- Ammo consumed, reload counts, and blocked-use counts
- Skill trigger counts and skill-attributed effect totals

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

### Phase 4.5: Combat Feature Extensions (Skills, Crit, Ammo)

- Extend API contract and schema for skills, crit stats, and ammo fields
- Add deterministic crit roll handling in the event engine
- Add ammo gate/reload behavior, including immediate-use-on-late-reload semantics
- Add player skill runtime with per-fight counters and one-time triggers
- Integrate new telemetry into run metrics and debug outputs

Status: not started.

Planned entry criteria:

- Project spec updates for Skills/Crit/Ammo are approved.
- Current deterministic baseline remains passing before extension work begins.

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
- Deterministic crit behavior for identical seed and payload
- Correct ammo gating/reload behavior under edge timing conditions
- Stable skill trigger ordering for simultaneous events

Current quality signal:

- `vp check` is clean.
- Core backend behavior has targeted tests for deterministic outcomes and status/timer interactions.
- Additional frontend interaction coverage and contract-regression tests are still needed as UX complexity grows.

## Next 30-60 Day Priorities

1. Implement core feature extension baseline (Skills/Crit/Ammo)

- Add contract models and schema for skills, crit, and ammo
- Implement deterministic crit roll + crit multiplier application
- Implement ammo consume/reload/immediate-use behavior
- Implement initial skill trigger runtime (counters + one-time conditions)
- Add backend tests covering requested example skill patterns

2. Harden simulator authoring UX

- Improve board interaction affordances (selection cues, move/cancel behavior, keyboard support)
- Add regression coverage for placement helpers and workspace transformations
- Ensure error guidance remains stable as backend contract details evolve

3. Improve analysis UX

- Expand comparison views with richer distribution summaries
- Add aggregated distributions/charts from batch results
- Add better filtering/export for combat logs and timer traces
- Surface crit/ammo/skill metrics in analysis UI

4. Strengthen validation and regression confidence

- Expand frontend validation aligned to backend schema constraints
- Add contract and determinism regression tests around high-risk mechanics
- Add frontend tests for API error mapping and section-level surfacing
- Add deterministic seed-regression tests for crit-roll streams

5. Prepare for scale phase entry

- Profile event-loop hotspots with larger synthetic batches
- Define deployment target and packaging checklist

## Notes

- The project spec is the source of truth for the combat model and design constraints
- The plan should stay broader than the spec and describe delivery priorities and status
- The immediate goal is to complete visual authoring and analysis workflows on top of the already functional deterministic engine
