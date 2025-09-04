# USA Badminton Junior Rankings

Ingest monthly Excel results, compute official‑style top‑4 rankings (with lower‑age carry‑up), and publish them via a FastAPI backend and a React UI. Run locally with **DynamoDB Local** or fully serverless on **AWS** (S3 → Lambda → DynamoDB).

<p align="center">
  <sub>Repository: <code>pitani/usa-badminton-rankings</code></sub>
</p>

---

## Table of contents
- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Repository structure](#repository-structure)
- [Quick start (local)](#quick-start-local)
- [API endpoints](#api-endpoints)
- [Ranking rules](#ranking-rules)
- [AWS (serverless path)](#aws-serverless-path)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Overview

This app manages and publishes **USA junior badminton rankings**. You upload a monthly spreadsheet and the system:
1) ingests the rows into DynamoDB,  
2) computes rankings per federation‑style rules (top‑4 in period, carry‑up from lower age if the player entered the higher age), and  
3) serves data via a REST API for a simple web UI.

- **Local dev**: Docker + DynamoDB Local, Python (FastAPI), React (Vite + Tailwind).
- **AWS**: Excel uploaded to S3 triggers a Lambda to ingest & rank; data lands in DynamoDB. Optional presign endpoint for secure uploads from the browser.

---

## Features

- **Excel ingestion** (expected headers):
  - `PlayerID, Event Name, FinishingPosition, Finishing Position Points, Tournament Type, Tournament Name, FirstName, LastName`
- **Ranking logic**:
  - For each player & event (e.g., `BS U17`), sum the **best 4** event points.
  - If the player played **at least one** higher‑age event, include lower‑age points in the candidate pool; still count only the **best 4** overall.
  - **Unique** ranks (no dense ties). Tie‑breakers: total points → per‑slot vector (best, 2nd, 3rd, 4th) → number of counted results → `LastName` → `FirstName`.
- **Browse & filter** UI with event pickers and rankings tables.
- **REST API** for events, rankings, and player results.

---

## Architecture

### Local
```
Excel → Ingestion (Python) → DynamoDB Local
                           ↘ Compute rankings → DynamoDB Local
FastAPI (read) → http://localhost:8008
React UI (read) → http://localhost:5173
```

### AWS (serverless)
```
Browser → Presigned PUT → S3 (uploads)
S3 ObjectCreated → Lambda (container: pandas/openpyxl)
                   → DynamoDB (Players, Events, Results, Rankings)
Optional: API Gateway for presign + read APIs, CloudFront for UI
```

---

## Repository structure

```
usa-badminton-rankings/
├─ backend/
│  ├─ api/
│  │  └─ main.py                 # FastAPI app (read endpoints)
│  ├─ infra/
│  │  └─ create_tables.py        # Create DynamoDB tables (local)
│  ├─ ingestion/
│  │  └─ ingest_simple.py        # Read Excel → write Players/Events/Results/Rankings
│  └─ .venv/                     # Local virtualenv (ignored)
├─ frontend/
│  ├─ index.html, src/, vite.config.ts, etc.
│  └─ .env.development           # VITE_API_BASE=http://localhost:8008
├─ infra/
│  └─ aws-sam/
│     ├─ template.yaml           # SAM template: S3 → Lambda → DynamoDB
│     ├─ Dockerfile              # Lambda container (pandas/openpyxl/boto3)
│     ├─ app/handler.py          # Ingest + rank Lambda
│     ├─ src/presign/app.py      # Presign URL Lambda (GET /presign)
│     └─ README_AWS.md           # Deploy & usage
├─ INSTALL-mac.md                # macOS install guide
├─ README.md                     # You are here
└─ .gitignore
```

---

## Quick start (local)

**macOS** users: full steps in `INSTALL-mac.md`. A condensed version:

```bash
# DynamoDB Local
docker rm -f ddb-local 2>/dev/null
docker run -d --name ddb-local -p 8000:8000 amazon/dynamodb-local:latest \
  -jar DynamoDBLocal.jar -sharedDb -inMemory

# Backend (venv + deps)
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -U pip setuptools wheel
backend/.venv/bin/python -m pip install boto3 pandas fastapi "uvicorn[standard]" openpyxl

# Env vars (Local DynamoDB)
export DDB_ENDPOINT=http://localhost:8000
export AWS_DEFAULT_REGION=us-east-1
export AWS_ACCESS_KEY_ID=dummy
export AWS_SECRET_ACCESS_KEY=dummy

# Create tables & ingest
backend/.venv/bin/python backend/infra/create_tables.py
backend/.venv/bin/python backend/ingestion/ingest_simple.py "/absolute/path/YourFile.xlsx"

# Run API (http://localhost:8008)
backend/.venv/bin/uvicorn backend.api.main:app --reload --port 8008

# Run UI (http://localhost:5173)
cd frontend
npm install
echo "VITE_API_BASE=http://localhost:8008" > .env.development
npm run dev
```

---

## API endpoints

Base URL (local): `http://localhost:8008`

- `GET /health` → `{"ok": true}`
- `GET /events`
- `GET /rankings?event=<EventCode>&limit=<N>`
- `GET /player-results?playerId=<ID>&event=<EventCode>`

> For AWS presigned uploads, see `infra/aws-sam/README_AWS.md` (`GET /presign` usage).

---

## Ranking rules

- **Top‑4** scoring: sum the highest 4 point results for the event.
- **Carry‑up**: If a player appears at least once in higher age (e.g., played `U17`), include their lower‑age results when computing that higher‑age total; still only **best 4** overall.
- **Unique ranks** (no dense ties). Tie‑breakers:
  1. Higher **TotalPoints**
  2. Better **Top4Vector**
  3. Higher **Counted**
  4. Alphabetical by **LastName**, then **FirstName**

---

## AWS (serverless path)

A minimal **SAM** project is included under `infra/aws-sam/`:
- Upload Excel to S3 (via presigned URL).
- S3 event triggers Lambda container (`pandas`, `openpyxl`, `boto3`) to ingest & rank.
- DynamoDB tables: `Players`, `Events`, `Results`, `Rankings`.

Deploy:
```bash
cd infra/aws-sam
sam build --use-container
sam deploy --guided
```


Copyright © 2025. All rights reserved.
