# Phase 2 Core Engine Execution Plan

## At a Glance

- Last updated: 2026-04-09
- Overall status: In progress
- Current phase: Phase 2 Core Engine
- Primary focus now: deterministic semantics and event ordering hardening

## Phase Status Dashboard

- [x] Phase 1 Contract and Scope
- [ ] Phase 2 Core Engine
- [ ] Phase 3 API and Frontend Integration
- [ ] Phase 4 Debugging and Analysis UX
- [ ] Phase 5 Scale and Packaging

## Current Baseline Entering Phase 2

- Implemented:
  - Simulation request and response contracts
  - Minimal discrete-event loop
  - Timed item use scheduling
  - Burn and poison status ticks
  - Regeneration event ticks
  - Structured API error envelope
  - Unified test command: vp run test:all
- Missing for Phase 2 completion:
  - Explicit deterministic tie-time event priority rules
  - Combat log output suitable for inspection and regression snapshots
  - Adjacency-aware target resolution
  - Hardened status stacking and reapplication semantics
  - Expanded deterministic regression suite for engine behavior

## Milestones and Deliverables

### M1 Deterministic Event Semantics

Status: In progress

Progress notes:

- Implemented explicit same-time event priority ordering in the engine queue comparator
- Implemented deterministic time-slice death resolution for simultaneous item-use events
- Added regression tests for simultaneous lethal item uses and same-time poison-vs-regen ordering
- Added foundational per-item and per-player metric breakdown structures for future visualization work

Deliverables:

- Define explicit same-time event priority ordering
- Encode ordering directly in event queue processing
- Define deterministic death-resolution and stop-condition rules
- Add edge-case tests for simultaneous events

Acceptance criteria:

- Same seed and same payload always produce the same winner, duration, and event order
- Determinism tests pass repeatedly in local runs

### M2 Combat Log and Inspection Surface

Status: Not started

Deliverables:

- Add structured per-run combat log entries to simulation results
- Include event time, type, source, target, and state delta
- Add optional log capping for batch efficiency

Acceptance criteria:

- Single-run responses contain an ordered event log
- Logs are stable and suitable for regression assertions

### M3 Adjacency and Target Resolution

Status: Not started

Deliverables:

- Add board adjacency utility functions
- Add deterministic target selection that can use adjacency
- Validate board interactions for item sizes and occupied slots

Acceptance criteria:

- At least one effect path uses adjacency-aware targeting
- Deterministic tie-breaking is documented and tested

### M4 Status Semantics Hardening

Status: Not started

Deliverables:

- Finalize burn and poison stacking rules
- Finalize reapply behavior and decay behavior
- Ensure regen and status ticks follow deterministic ordering

Acceptance criteria:

- Stacking and reapply scenarios are covered by unit tests
- No ambiguous behavior remains in status tick processing

### M5 Regression and Performance Guardrails

Status: Not started

Deliverables:

- Add scenario-based regression tests for representative fights
- Add run stop-reason metadata for time and event caps
- Add lightweight performance guardrails for batch simulations

Acceptance criteria:

- Regression suite catches event ordering or mechanic drift
- Batch simulations remain stable for moderate run counts

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
