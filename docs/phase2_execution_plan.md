# Phase 2 Core Engine Execution Plan

## At a Glance

- Last updated: 2026-04-09
- Overall status: **Phase 2 Complete** (M1–M5 all complete)
- Current phase: Phase 2 Core Engine
- Primary focus now: Ready for Phase 3 API and Frontend Integration

## Phase Status Dashboard

- [x] Phase 1 Contract and Scope
- [x] Phase 2 Core Engine
- [ ] Phase 3 API and Frontend Integration
- [ ] Phase 4 Debugging and Analysis UX
- [ ] Phase 5 Scale and Packaging

## Phase 2 Complete — Ready for Phase 3

All core engine systems implemented and hardened:

- Implemented:
  - Discrete-event simulation loop with deterministic event ordering
  - Timed item-use scheduling with cooldown and initial-delay support
  - Status mechanics: burn (3% decay with 1 minimum), poison (persistent), regeneration (tick-based)
  - Board adjacency utilities and deterministic target resolution
  - Combat log with per-event state deltas and optional capping
  - Structured metrics per item and per player
  - Stop-reason tracking (natural_win, time_limit_exceeded, event_limit_exceeded)
  - Batch performance monitoring (total events, average per run, stop reason breakdown)
  - Comprehensive regression test suite (27 unit tests covering edge cases and scenarios)
  - Full API contract with Pydantic models and generated TypeScript types

- Test Status: All 27 backend tests passing
- Build Status: Frontend and backend build successfully
- Type Safety: TypeScript types fully generated and current
- Determinism: Verified—same seed and payload always produce identical results

## Milestones and Deliverables

### M1 Deterministic Event Semantics

Status: Complete ✅

Progress notes:

- Implemented explicit same-time event priority ordering in the engine queue comparator (item_use=0, burn_tick=1, poison_tick=2, regen_tick=3, with player-order tie-breaking)
- Implemented deterministic time-slice death resolution for simultaneous item-use events (alive_at_time snapshot)
- Added regression tests: simultaneous lethal item uses → draw outcome, same-time poison-vs-regen ordering, metrics structure validation
- Added foundational per-item and per-player metric breakdown structures (damage split by type, status event tracking, per-item instance attribution)
- Built frontend request/response inspector for simulation visibility (prettified metrics, raw JSON)
- Documented metrics contract in README and project spec
- All 10 backend unit tests passing; TypeScript clean; build successful

Deliverables:

- Define explicit same-time event priority ordering
- Encode ordering directly in event queue processing
- Define deterministic death-resolution and stop-condition rules
- Add edge-case tests for simultaneous events

Acceptance criteria: ✅ **ALL MET**

- ✅ Same seed and same payload always produce the same winner, duration, and event order (validated)
- ✅ Determinism tests pass repeatedly in local runs (10/10 backend tests passing)
- ✅ Edge cases (simultaneous events, status ordering) covered by regression suite
- ✅ Metrics deterministic and suitable for future visualization (per-item damage breakdown, status tracking)

### M2 Combat Log and Inspection Surface

Status: Complete ✅

Progress notes:

- Added structured per-run `combat_log` entries to simulation results with deterministic event ordering
- Added event-level fields: `time_seconds`, `event_type`, `source_player_id`, `source_item_instance_id`, `target_id`
- Added per-event `state_deltas` for health, shield, burn, and poison transitions
- Added optional request-level `combat_log_limit` capping with `combat_log_total_events` and `combat_log_truncated` metadata
- Added backend regression tests for log ordering, state delta correctness, and capping behavior
- Exposed combat log preview in the frontend simulator inspection surface

Deliverables:

- Add structured per-run combat log entries to simulation results
- Include event time, type, source, target, and state delta
- Add optional log capping for batch efficiency

Acceptance criteria: ✅ **ALL MET**

- ✅ Single-run responses contain an ordered event log
- ✅ Logs are stable and suitable for regression assertions

### M3 Adjacency and Target Resolution

Status: Complete ✅

Progress notes:

- Added runtime board utilities for placement validation and adjacency lookup generation
- Added deterministic opponent target-anchor selection with explicit tie-break ordering (adjacent-first, then nearest distance, then start slot, then lexical item instance id)
- Routed timed item-use effect targeting through the deterministic resolver and exposed resolved anchors in item-use combat-log entries
- Hardened board validation with duplicate item instance id detection in addition to occupied-slot and bounds checks
- Added backend regression tests for adjacency preference, deterministic tie-breaking, and duplicate instance-id validation

Deliverables:

- Add board adjacency utility functions
- Add deterministic target selection that can use adjacency
- Validate board interactions for item sizes and occupied slots

Acceptance criteria:

- ✅ At least one effect path uses adjacency-aware targeting
- ✅ Deterministic tie-breaking is documented and tested

### M4 Status Semantics Hardening

Status: Done

Progress notes:

- Implemented burn tick decay using the spec rule of 3% rounded up with a minimum reduction of 1
- Implemented poison tick persistence so poison no longer decays on its own during tick processing
- Implemented shield-mitigated burn tick damage without consuming shield, and poison tick damage that bypasses shield entirely
- Implemented healing-based status reduction for burn and poison, while keeping regeneration exempt from status reduction
- Added regression tests for burn decay, poison persistence, and heal-versus-regen status reduction behavior

Deliverables:

- Finalize burn and poison stacking rules
- Finalize reapply behavior and decay behavior
- Ensure regen and status ticks follow deterministic ordering

Acceptance criteria:

- ✅ Stacking and reapply scenarios are covered by unit tests
- ✅ No ambiguous behavior remains in status tick processing

### M5 Regression and Performance Guardrails

Status: Complete ✅

Progress notes:

- Implemented `RunStopReason` enum with three values: `natural_win`, `time_limit_exceeded`, `event_limit_exceeded`
- Added `stop_reason` field to `SimulationRunResult` to track why each run terminated
- Updated simulation loop to detect and assign stop reason based on exit condition (living player count, time cap, or event cap)
- Added `BatchPerformanceMetrics` to track aggregate performance:
  - `total_events_across_batch`: sum of all events processed across all runs
  - `average_events_per_run`: mean events per run
  - `stop_reason_breakdown`: histogram of stop reasons for the batch
- Created 7 new regression scenario tests covering representative combat patterns:
  - Natural win via lethal damage
  - Time limit exceeded (slow DoT race)
  - Event limit exceeded (rapid item cadence)
  - Aggressive damage race (both players dealing high damage)
  - Defensive healing mirror (both players healing, expecting draw)
  - Multi-item complexity (staggered items with mixed effects)
  - Batch performance with 100 deterministic runs
- Verified performance metrics are populated and consistent in batch summaries
- All 27 backend unit tests passing; build and type generation successful

Deliverables:

- ✅ Add scenario-based regression tests for representative fights
- ✅ Add run stop-reason metadata for time and event caps
- ✅ Add lightweight performance guardrails for batch simulations

Acceptance criteria: ✅ **ALL MET**

- ✅ Regression suite includes 7+ tests covering deterministic battles, limit scenarios, and batch performance
- ✅ Stop reason metadata is deterministic and suitable for monitoring and regression detection
- ✅ Batch simulations remain stable: 100 runs complete successfully with performance tracking

## Implementation Sequence

1. M1 deterministic event semantics
2. M2 combat log output
3. M3 adjacency and targeting
4. M4 status semantics hardening
5. M5 regression and performance guardrails

## Testing Gate for Every Milestone

1. Run backend tests: vp run test:backend
2. Run combined tests: vp run test:all
3. Run frontend build check: vp run build
4. Regenerate API types if contracts changed: vp run gen:api

## Working Rules for Agents

- Keep item behavior data-driven and avoid one-off item hacks
- Keep backend deterministic for identical seed and payload
- Prefer minimal incremental changes over broad rewrites
- Update this file when milestone status changes
- Include validation evidence in each milestone pull request
