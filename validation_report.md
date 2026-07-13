# Validation Report — Enterprise Conversational AI Platform

**Date:** 2026-07-14
All commands below were actually executed in a sandboxed clone of the repo; raw output is quoted, not paraphrased from memory.

---

## 1. Backend environment & startup

```
python3 -m venv .venv
pip install -r requirements.txt      # clean install, no errors
python -c "from backend.main import app"   # imports cleanly, engine initializes:
  ✅ Engine initialized successfully
```

## 2. Static analysis

```
python3 -m pyflakes backend/main.py lib/engine_executor.py lib/flight_engine.py
```
Result: **0 findings** (previously: 1 unused import, 2 empty f-strings, 1 unused local, 6 undefined-name errors in dead code — all fixed/removed).

## 3. API tests (required by mission spec)

Server run: `uvicorn backend.main:app --host 0.0.0.0 --port 8002`

| Test | Result | Reply (human-readable, no raw JSON/dict) |
|---|---|---|
| `GET /` | 200 OK | `{"status":"healthy"}` |
| `GET /test` | 200 OK | Clean 3-segment CRUISE breakdown (was 6, incl. junk, before fix) |
| `POST /query {"query":"flight overview"}` | 200 OK, `validation_passed: true` | "The flight ran 52m 51s, from ... Altitude ranged from 1682.3 to 5196.6 ft (avg 3574.1 ft). Airspeed ranged from -0.0 to 106.2 knots (avg 71.8 knots). Ground speed ranged from 0.0 to 125.2 knots (avg 76.1 knots). Phase breakdown: TAXI (9m 29s), TAKEOFF (1m 9s), CLIMB (5m 12s), CRUISE (29m 39s), DESCENT (6m 8s), APPROACH (0m 26s), LANDING (0m 37s)." |
| `POST /query {"query":"cruise duration"}` | 200 OK | "CRUISE lasted 29m 39s across 3 segment(s)." |
| `POST /query {"query":"safety analysis"}` | 200 OK | "Safety analysis completed. 0 issue(s) require review." |
| `POST /dialogflow/webhook {"text":"flight overview"}` | 200 OK | `fulfillment_response.messages[0].text.text[0]` = same clean sentence as above; `sessionInfo.parameters` = `{"intent":"flight_overview","phase":null,"success":true}` (small & flat, not the full nested payload) |
| `POST /dialogflow/webhook {"text":"cruise duration"}` | 200 OK | "CRUISE lasted 29m 39s across 3 segment(s)."; `sessionInfo.parameters` = `{"intent":"phase_duration","phase":"CRUISE","success":true}` |
| `POST /query {"query":""}` (edge case) | **400** `{"detail":"Query text must not be empty."}` | Correct rejection, no crash |
| `POST /dialogflow/webhook` with invalid JSON body (edge case) | **400** `{"detail":"Invalid JSON: ..."}` | Correct rejection, no crash |

**Critical requirement check:** No response in any test contains a raw Python dict repr, raw JSON blob standing in for a reply, or internal engine structure exposed as the user-facing message. All `reply` / `fulfillment_response` text fields are natural-language sentences.

## 4. Engine / data validation

```
Rows loaded: 3172
Duplicate rows: 0
Segments after fix: 12   (was 25, with 10 spurious 1-row/UNKNOWN segments)
Distinct phases present: ['APPROACH','CLIMB','CRUISE','DESCENT','LANDING','TAKEOFF','TAXI']  (all 7 expected phases present, 0 UNKNOWN)
Sum of segment durations: 3160s | Flight total duration: 3171s  (11s gap is expected boundary rounding across 12 segments, not a data-loss bug)
```

## 5. Frontend

```
pnpm install --frozen-lockfile     # succeeds after fixing pnpm-workspace.yaml placeholder
./node_modules/.bin/tsc --noEmit   # 0 errors
./node_modules/.bin/next build     # ✓ Compiled successfully in ~9.5s
                                    # Routes: / (static), /_not-found (static), /api/chat (dynamic)
```

## 6. Webhook/Dialogflow contract checks
- `fulfillment_response.messages[].text.text[]` — correct Dialogflow CX shape. ✅
- `sessionInfo.parameters` — now small and flat (`intent`, `phase`, `success`), no longer a multi-KB nested dump. ✅
- Invalid JSON body → clean 400, not a 500/stack trace. ✅
- Fallback handling for unmatched intent → returns a plain-English "try asking about..." message, not an error object. ✅ (see `lib/engine_executor.py` fallback branch, unchanged, already correct)

## 7. Residual/non-blocking observations
- `lib/llm_router.py` / `lib/llm_rephraser.py` / `lib/validation_layer.py` are present but unused by the live API (see audit report — left in place, not a validation failure).
- No automated test suite (pytest/jest) exists in the repo to run as regression coverage going forward; all validation above was done via live server + manual API calls. Recommend adding a pytest suite for `lib/engine_executor.py` and `backend/main.py` as a follow-up.
