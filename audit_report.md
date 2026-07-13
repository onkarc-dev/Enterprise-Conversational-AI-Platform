# Audit Report — Enterprise Conversational AI Platform

**Date:** 2026-07-14
**Auditor:** Claude (staff engineer session), running in an isolated sandbox against a fresh clone of `main`
**Method:** Every finding below was reproduced by actually running the code (not inferred from reading alone), then fixed, then re-run to confirm the fix.

---

## Scope note

This session audited the repo as cloned from GitHub into a Linux sandbox. It does **not** have access to the Windows path originally referenced (`C:\Enterprise-Conversational-AI-Platform\...`) — that's the user's local machine. All commands below were run against `/home/claude/Enterprise-Conversational-AI-Platform`.

---

## Critical issues found and fixed

### 1. Webhook/chat replies leaked raw Python dict text (CRITICAL)
**Where:** `backend/main.py`, `format_engine_response()`
**Symptom:** `POST /query {"query":"flight overview"}` returned a `reply` field that was the literal `str()` of a nested Python dict — single-quoted keys, `{...}` braces, nested lists of dicts — pasted straight into what's supposed to be a conversational answer. The Dialogflow webhook forwarded that same raw text as the `fulfillment_response` message a real user would see.
**Root cause:** `format_engine_response()` only special-cased three result shapes and fell back to `str(result)` for everything else, including the biggest/most common one (`flight_overview`).
**Fix:** Rewrote `format_engine_response()` to explicitly handle every result shape the engine can return (flight overview, phase duration, phase overview, single metric value, phase list, summary-style results), with a generic fallback that summarizes scalar fields in "key: value" sentences instead of ever printing a raw structure.
**Verified:** Re-ran all required test queries; every `reply` is now a plain English sentence. See `validation_report.md`.

### 2. Docker/deployment config built and ran a different, broken backend (CRITICAL)
**Where:** `Dockerfile.backend`, `docker-compose.yml`, `scripts/backend_server.py`
**Symptom:** The production Docker image built `scripts/backend_server.py`, a **Flask** app on port 5000 with a completely different route set (`/api/query`, `/api/health`, etc.) than the FastAPI app (`backend/main.py`, port 8000) that the frontend, README, and this mission's own test plan all target. Worse, `flask`/`flask-cors` were never installed by `requirements.txt`, so this container would fail at import time if built.
**Root cause:** Legacy artifact from an earlier architecture iteration that was never removed when the FastAPI backend became canonical.
**Fix:** Deleted `scripts/backend_server.py`. Rewrote `Dockerfile.backend` to build/run `uvicorn backend.main:app` on port 8000, and `docker-compose.yml` to match (port 8000, health check hits `GET /`).
**Verified:** `backend/main.py` imports and runs cleanly under the new command; frontend already defaulted to port 8000 (`NEXT_PUBLIC_API_URL`/`FASTAPI_URL` fallback in `app/api/chat/route.ts` and `lib/query-processor.ts`), confirming FastAPI was always the intended target.

### 3. Spurious "1 rows" / `UNKNOWN` phase segments (MAJOR, data quality)
**Where:** `lib/flight_engine.py`, `create_segments()`
**Symptom:** `GET /test` and `phase_duration`/`flight_overview` results showed CRUISE split into 6 segments, several with `duration_formatted: "1 rows"` and phase `"UNKNOWN"`.
**Root cause:** 10 rows out of 3,172 in `rule_labelled.csv` have a missing (`NaN`) `Phase` label — momentary labeling dropouts, not real phase transitions. Because segmentation splits on every value change in `Phase` (including `NaN`), each isolated `NaN` row split one continuous phase into three fragments (before / 1-row-NaN / after).
**Fix:** `create_segments()` now forward/backward-fills isolated `NaN` `Phase` values before computing segment IDs, so momentary data gaps no longer fracture real phases.
**Verified:** Segment count for the sample flight went from 25 (10 spurious/UNKNOWN) to **12 correct segments**, all with real phase labels, 0 `UNKNOWN`, 0 "1 rows". Confirmed no data was lost (row count and duplicate-row checks unchanged).

### 4. Undefined-variable bugs in dead code (MAJOR — would have been a runtime crash if ever called)
**Where:** `lib/flight_engine.py`, `DynamicFlightCalculator.answer()`, `.parse_query()`, `.parse_question()`
**Symptom:** Static analysis (`pyflakes`) found references to undefined names `segment` and `segment_durations`, and a call to a nonexistent `parse_standard_question` guarded by `hasattr` (i.e., permanently unreachable).
**Root cause:** These methods were legacy code from an interactive CLI harness (`if __name__ == "__main__": ...`) that was never wired into the live API — `backend/main.py` / `lib/engine_executor.py` use their own `infer_intent()` + `execute_query()` instead, and never call `engine.answer()`.
**Fix:** Removed the dead `answer()`, `parse_query()`, `parse_question()` methods and the CLI debug block at the bottom of the file (523 lines total). Verified with `grep` that nothing else calls them before deleting.
**Verified:** `pyflakes` reports zero errors on `backend/main.py`, `lib/engine_executor.py`, `lib/flight_engine.py` after the change; full API regression suite re-run and still passes.

### 5. Oversized/duplicate session payload sent to Dialogflow (MODERATE)
**Where:** `backend/main.py`, `dialogflow_webhook()`
**Symptom:** `sessionInfo.parameters.result` echoed the *entire* nested engine result back into Dialogflow CX session state — for `flight_overview` this is a multi-KB nested structure with a list of 25 segment dicts.
**Fix:** Trimmed session parameters to `intent`, `phase`, `success` — small, flat, and actually useful for a CX flow to branch on.

### 6. Duplicate/dead files
- `backend/requirements.txt` was a near-duplicate of the root `requirements.txt` (same packages, different comments) → removed, root file is canonical.
- `backend/rule_labelled.csv` (4KB, different content, unreferenced anywhere in code) → removed.
- `public/rule_labelled.csv` (1.6MB byte-identical duplicate of the root CSV, unreferenced by any frontend code) → removed.
- `scripts/backend_server.py` → removed (see #2); the now-empty `scripts/` directory was also removed.

### 7. `/query` endpoint had no input validation or exception handling
**Where:** `backend/main.py`
**Fix:** Added a 400 response for empty/whitespace queries and wrapped intent inference + query execution in a try/except that returns a 500 with a clear message instead of an unhandled stack trace.

### 8. `pnpm-workspace.yaml` shipped with a literal unfinished placeholder
**Found:** `allowBuilds: sharp: set this to true or false` — this is template text, not valid config, and caused `pnpm install`/`pnpm run` to fail outright in a clean environment.
**Fix:** Replaced with a correct `onlyBuiltDependencies: [sharp]` entry.

---

## Verified working (no changes needed)
- FastAPI backend imports and starts cleanly; engine initializes over the real CSV with no errors.
- All engine data is now free of duplicate rows (0 duplicates in 3,172 rows) and covers all 7 expected phases (TAXI, TAKEOFF, CLIMB, CRUISE, DESCENT, APPROACH, LANDING).
- Frontend TypeScript typecheck (`tsc --noEmit`) passes with zero errors.
- Next.js production build succeeds (`next build`, Turbopack), all 4 routes compile.
- `app/api/chat/route.ts` correctly proxies to the FastAPI backend, prefers the (now-fixed) human-readable `reply` field, and has real error/loading state handling in `components/chat-interface.tsx`.
- CORS, request/response schemas, and Dialogflow `fulfillment_response`/`sessionInfo` structure all match Dialogflow CX's expected webhook contract.

## Known remaining items (not blocking, flagged for visibility)
- `lib/llm_router.py`, `lib/llm_rephraser.py`, `lib/validation_layer.py` exist in the repo and are referenced in `README.md`/`PROJECT_COMPLETE.md`/`QUICKSTART.md`/`BUILD_SUMMARY.md` as part of the intended architecture, but are **not currently imported or called anywhere** in the live FastAPI backend — `backend/main.py` uses its own lightweight keyword-based `infer_intent()` instead. This looks like an intentional "future LLM-routing" module the team hasn't wired in yet rather than dead code, so it was left in place and only flagged here rather than deleted — worth a decision from the team on whether to wire it in or remove it.
- The generic fallback branch in `format_engine_response()` (for any future/unexpected engine result shape) still can't guarantee crafted phrasing for arbitrary new shapes — it degrades gracefully to "key: value" sentences rather than a narrative, which is a reasonable safety net but should be extended if new intents are added.
