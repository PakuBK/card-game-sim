---
name: fallow-analysis
description: 'Run fallow codebase intelligence (dead code, duplication, complexity health, audit) via Vite+ (`vp exec fallow`) and summarize actionable findings. Use when: reviewing changes, cleaning up unused exports/files/deps, spotting duplication, checking complexity hotspots, or running a quick quality gate alongside `vp check`.'
argument-hint: 'summary | json | audit [--base <ref>]'
---

# Fallow Analysis

Use `fallow` to analyze the JS/TS codebase as a whole (unused files/exports/deps, duplication, and complexity health).

## When to use

- After implementing a feature/refactor to catch dead code, duplication, or complexity regressions.
- Before opening a PR, alongside `vp check` / `vp test`.
- When debugging “why is this here?” or “can I delete this?” questions.

## Commands (use Vite+ wrapper)

Prefer `vp exec` so the repo-local `node_modules/.bin/fallow` is used.

### 1) Quick human summary (fast)

- Run: `vp exec fallow --summary`
- If it exits non-zero: that typically means it found issues (still useful for analysis).

### 2) Focused analysis

- Dead code only: `vp exec fallow dead-code`
- Duplication only: `vp exec fallow dupes`
- Complexity/health only: `vp exec fallow health`

Tip: `vp exec fallow health --top 20` is good for finding refactor targets.

### 3) Structured output for agents

- JSON (all analyses): `vp exec fallow --format json`
- JSON (audit gate): `vp exec fallow audit --format json`

Interpretation guidance:
- `audit` returns a `verdict` (pass/warn/fail) in JSON.
- A non-zero exit code usually indicates a `fail` verdict or issues found.

## Agent procedure (what to do with results)

1. Run `vp exec fallow --summary`.
2. If the summary flags specific files, open those files first and prefer small, safe fixes (delete unused exports, remove unused deps, dedupe small blocks, etc.).
3. If you need machine-actionable data (or the user asked for “details”), rerun with JSON:
   - `vp exec fallow --format json`
   - Summarize: counts per category + top 3 actionable items (highest impact, lowest risk).
4. If the user wants a gate similar to `vp check`, run:
   - `vp exec fallow audit --format json`
   - Report verdict and why (dead-code vs dupes vs health).

## Notes

- `fallow` is expected to find issues in many repos on first adoption; treat it as a prioritization tool unless the user asks to enforce it as a hard gate.
- In this repo, `vp exec fallow --summary` is known to work.
