# Deployment

## Prerequisites

- Python 3.10 or newer.
- Node.js compatible with Next.js 16.
- pnpm.
- `rule_labelled.csv` present at the repository root.

## Backend

Install dependencies:

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

Run FastAPI from the backend directory:

```powershell
cd backend
..\venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000
```

Health check:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/ -UseBasicParsing
```

Expected response:

```json
{"status":"healthy"}
```

## Frontend

Install dependencies:

```powershell
pnpm install
```

Configure backend URL if it is not `http://127.0.0.1:8000`:

```powershell
$env:FASTAPI_URL="https://your-backend.example.com"
$env:NEXT_PUBLIC_API_URL="https://your-backend.example.com"
```

Build:

```powershell
pnpm build
```

Run:

```powershell
pnpm start
```

## Production Notes

- Set `CORS_ORIGINS` on the backend to the deployed frontend origin.
- Keep `.env.local` out of git.
- Serve FastAPI behind a reverse proxy or managed platform with TLS.
- Run backend and frontend as separate supervised services.
