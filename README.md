# USAB Junior Rankings — Monorepo

This repository packages everything you need to run the app **anywhere**:

- **DynamoDB** (Local for dev; AWS for prod)
- **FastAPI** backend
- **React + Vite + Tailwind** frontend
- Ingestion pipeline to compute rankings from your Excel

See the root README in the previous message for full local setup. Quick commands:

```bash
# 0) start DynamoDB (Docker)
docker compose up -d

# 1) backend venv + deps
cd backend/ingestion && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2) env for local
export DDB_ENDPOINT=http://localhost:8000
export AWS_DEFAULT_REGION=us-east-1
export AWS_ACCESS_KEY_ID=dummy
export AWS_SECRET_ACCESS_KEY=dummy

# 3) create tables + ingest
python create_tables.py
python ingest_simple.py "/absolute/path/YourFile.xlsx"

# 4) run API
uvicorn backend.api.main:app --reload --port 8008

# 5) run UI
cd ../../frontend && npm install && npm run dev
```

## Repo layout

```
backend/
  ingestion/
    ingest_simple.py
    create_tables.py
    requirements.txt
  api/
    main.py
frontend/
  package.json
  src/
.github/workflows/ci.yml
docker-compose.yml
README.md
```

## Push to GitHub

1. Create a repo on GitHub (or use GitHub CLI):
   ```bash
   gh repo create yourname/usab-rankings --public --source . --remote origin --push
   ```
   Or:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin git@github.com:yourname/usab-rankings.git
   git push -u origin main
   ```
