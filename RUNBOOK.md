# Runbook

## Local Startup

1. Start FastAPI:

```powershell
cd C:\Enterprise-Conversational-AI-Platform\Enterprise-Conversational-AI-Platform\backend
..\venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000
```

2. Start Next.js:

```powershell
cd C:\Enterprise-Conversational-AI-Platform\Enterprise-Conversational-AI-Platform
pnpm dev
```

3. Open `http://localhost:3000`.

## Smoke Tests

Backend health:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/ -UseBasicParsing
```

Engine smoke:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/test -UseBasicParsing
```

Dialogflow webhook smoke:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/dialogflow/webhook -Method POST -ContentType 'application/json' -Body '{"fulfillmentInfo":{"tag":"phase_duration"},"sessionInfo":{"parameters":{"phase":"CRUISE"}},"text":"How long was cruise?"}' -UseBasicParsing
```

Frontend API route smoke:

```powershell
Invoke-RestMethod http://localhost:3000/api/chat -Method POST -ContentType 'application/json' -Body '{"message":"Phase duration for cruise"}'
```

## Validation Commands

```powershell
.\venv\Scripts\python.exe -m py_compile backend\main.py
.\venv\Scripts\python.exe -m py_compile lib\engine_executor.py
.\venv\Scripts\python.exe -m py_compile lib\flight_engine.py
pnpm lint
pnpm build
```

## Common Failures

- `Phase column not found`: verify the root `rule_labelled.csv` is present and not replaced by the smaller backend CSV.
- `Connection refused` from `/api/chat`: start FastAPI or set `FASTAPI_URL`.
- `pnpm.ps1 cannot be loaded`: use `pnpm.cmd` on restricted PowerShell systems.
- Google font fetch failures: the app uses local CSS fonts now; this should not block builds.
