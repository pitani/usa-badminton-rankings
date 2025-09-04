# USAB Junior Rankings — Monorepo

- **DynamoDB** (Local for dev; AWS for prod)
- **FastAPI** backend
- **React + Vite + Tailwind** frontend
- Ingestion pipeline to compute rankings from the Excel

# Installation & Setup Guide

This doc explains how to run the **USAB Junior Rankings** app on a fresh computer.

Contents:
- [Prerequisites](#prerequisites)
- [Clone the repository](#clone-the-repository)
- [Start DynamoDB Local](#start-dynamodb-local)
- [Backend setup (Python + API)](#backend-setup-python--api)
- [Create tables](#create-tables)
- [Ingest your Excel](#ingest-your-excel)
- [Run the API](#run-the-api)
- [Run the UI](#run-the-ui)
- [One-liner quick start](#one-liner-quick-start)
- [Troubleshooting](#troubleshooting)
- [Useful commands](#useful-commands)
- [AWS deployment (very short outline)](#aws-deployment-very-short-outline)

---

## Prerequisites

**All platforms**
- Docker Desktop (for local DynamoDB)
- Git

**Backend**
- Python **3.10+** (3.11 recommended)

**Frontend**
- Node.js **20+** (LTS)
  - Recommended: install via `nvm`  
    ```bash
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
    nvm install --lts
    nvm use --lts
    node -v && npm -v
    ```

## Clone the repository

**HTTPS (no SSH key needed):**

git clone https://github.com/saishapitani/usab-rankings.git
cd usab-rankings

SSH (if you’ve set up a GitHub SSH key):

git clone git@github.com:saishapitani/usab-rankings.git
cd usab-rankings

## Start DynamoDB Local

# stop any old instance (ignore error if none)
docker rm -f ddb-local 2>/dev/null

# start in-memory DynamoDB Local
docker run -d --name ddb-local -p 8000:8000 amazon/dynamodb-local:latest \
  -jar DynamoDBLocal.jar -sharedDb -inMemory

# quick check (HTTP/1.1 400 is expected)
curl -sI http://localhost:8000/ | head -n1

## Backend setup (Python + API)

## Create a single virtualenv for all backend code at backend/.venv and install deps.

# from repo root
python3 -V || brew install python

python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -U pip setuptools wheel

# install required packages (no requirements.txt needed)
backend/.venv/bin/python -m pip install boto3 pandas fastapi "uvicorn[standard]" openpyxl

## Environment variables (Local DynamoDB)

## Set these in every terminal where you run backend commands:

export DDB_ENDPOINT=http://localhost:8000
export AWS_DEFAULT_REGION=us-east-1
export AWS_ACCESS_KEY_ID=dummy
export AWS_SECRET_ACCESS_KEY=dummy

## Create tables - The script is at backend/infra/create_tables.py.

backend/.venv/bin/python backend/infra/create_tables.py

## Ingest your Excel -  Expected columns (first sheet): PlayerID, Event Name, FinishingPosition, Finishing Position Points, Tournament Type, Tournament Name, FirstName, LastName

backend/.venv/bin/python backend/ingestion/ingest_simple.py "/absolute/path/YourFile.xlsx"

## Run the API

backend/.venv/bin/uvicorn backend.api.main:app --reload --port 8008

# test:
# curl http://127.0.0.1:8008/health

## API endpoints to try:

GET /events
GET /rankings?event=BS%20U17&limit=50
GET /player-results?playerId=1020191&event=BS%20U17

## Run the UI

cd ui
npm install
echo "VITE_API_BASE=http://localhost:8008" > .env.development
npm run dev

## Quick Start

# repo root
docker rm -f ddb-local 2>/dev/null
docker run -d --name ddb-local -p 8000:8000 amazon/dynamodb-local:latest -jar DynamoDBLocal.jar -sharedDb -inMemory
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -U pip setuptools wheel
backend/.venv/bin/python -m pip install boto3 pandas fastapi "uvicorn[standard]" openpyxl
export DDB_ENDPOINT=http://localhost:8000 AWS_DEFAULT_REGION=us-east-1 AWS_ACCESS_KEY_ID=dummy AWS_SECRET_ACCESS_KEY=dummy
backend/.venv/bin/python backend/infra/create_tables.py
backend/.venv/bin/python backend/ingestion/ingest_simple.py "/absolute/path/YourFile.xlsx"
backend/.venv/bin/uvicorn backend.api.main:app --reload --port 8008

## Useful commands

## List tables (Local):
aws dynamodb list-tables --endpoint-url http://localhost:8000 --region us-east-1

## Delete all local tables:

for t in $(aws dynamodb list-tables --endpoint-url http://localhost:8000 --query 'TableNames[]' --output text); do
  aws dynamodb delete-table --table-name "$t" --endpoint-url http://localhost:8000
done

## Start/stop fresh DB:

docker rm -f ddb-local
docker run -d --name ddb-local -p 8000:8000 amazon/dynamodb-local:latest -jar DynamoDBLocal.jar -sharedDb -inMemory

