---
name: vp-check
description: 'Run Vite+ quality checks with `vp check` and report actionable results. Use when: validating local changes, pre-PR quality gates, reproducing lint/type/format failures, or confirming a clean baseline before new work.'
argument-hint: 'optional scope (for example: changed files only, full workspace)'
---

# VP Check

Run the repo quality gate through Vite+ using `vp check`.

## When to use

- Before opening a PR.
- After implementing or refactoring a feature.
- When the user asks whether the workspace is "clean".
- After dependency or config changes that can affect formatting, linting, or TypeScript checks.

## Procedure

1. Confirm the working directory is the repository root.
2. Run `vp check`.
3. If `vp check` exits with code `0`:
- Report success and confirm the workspace passed format, lint, and type checks.
4. If `vp check` exits non-zero:
- Capture the failing sections and summarize by category (format, lint, typecheck).
- Prioritize the first actionable error per file.
- Apply focused fixes only in relevant files.
- Re-run `vp check` until it passes or a blocker is confirmed.

## Decision points

- If failures are only formatting-related:
- Prefer the standard formatter flow (for example, `vp fmt`) and re-run `vp check`.
- If failures include lint or type errors:
- Fix root causes first (types/imports/logic), then re-run `vp check`.
- If errors are unrelated to the current task:
- Do not silently rewrite broad areas; call out the pre-existing issues and ask whether to include them in scope.

## Completion criteria

- `vp check` returns exit code `0`.
- Any code edits made to satisfy checks are minimal and scoped.
- Final report includes:
- Outcome (pass/fail)
- Commands run
- Key fixed files (if any)
- Remaining blockers (if any)

## Notes

- Use Vite+ commands (`vp ...`) rather than direct package-manager or tool-specific binaries.
- If available, pair this with `vp test` for broader confidence after `vp check` passes.
