# macOS Installation Guide — USA Badminton Rankings

This guide shows how to set up and run the app **locally on macOS** using DynamoDB Local.


## 1) Prerequisites (macOS)

```bash
# Homebrew (if you don't have it)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Ensure Homebrew is on PATH (Apple Silicon)
echo $PATH | grep /opt/homebrew/bin >/dev/null || \
  (echo 'export PATH="/opt/homebrew/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc)

# Docker Desktop
brew install --cask docker
open -a "Docker"   # start Docker; wait until it's running

# Git
brew install git

# Python 3 (if needed)
brew install python

# Node.js via nvm (recommended)
brew install nvm
mkdir -p ~/.nvm
echo 'export NVM_DIR="$HOME/.nvm"' >> ~/.zshrc
echo '[ -s "/opt/homebrew/opt/nvm/nvm.sh" ] && . "/opt/homebrew/opt/nvm/nvm.sh"' >> ~/.zshrc
source ~/.zshrc
nvm install --lts
nvm use --lts
node -v && npm -v
```


---

## 2) Clone the repository

```bash
# HTTPS (no SSH key required)
git clone https://github.com/pitani/usa-badminton-rankings.git
cd usa-badminton-rankings
```

(SSH alternative: `git clone git@github.com:pitani/usa-badminton-rankings.git`)

---

## 3) Start DynamoDB Local

```bash
# stop any old instance (ignore error if none)
docker rm -f ddb-local 2>/dev/null

# start in-memory DynamoDB Local
docker run -d --name ddb-local -p 8000:8000 amazon/dynamodb-local:latest \
  -jar DynamoDBLocal.jar -sharedDb -inMemory

# quick check (HTTP/1.1 400 is expected)
curl -sI http://localhost:8000/ | head -n1
```

---

## 4) Backend setup (Python + FastAPI)

Create a virtual environment **inside the repo**:

```bash
# from repo root
python3 -V
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -U pip setuptools wheel

# install required packages
backend/.venv/bin/python -m pip install boto3 pandas fastapi "uvicorn[standard]" openpyxl
```

Set environment variables for **Local DynamoDB** (do this in every new terminal where you run backend commands):

```bash
export DDB_ENDPOINT=http://localhost:8000
export AWS_DEFAULT_REGION=us-east-1
export AWS_ACCESS_KEY_ID=dummy
export AWS_SECRET_ACCESS_KEY=dummy
```

---

## 5) Create tables

```bash
backend/.venv/bin/python backend/infra/create_tables.py
```

---

## 6) Ingest your Excel

Expected columns (first sheet, exact headers):
```
PlayerID, Event Name, FinishingPosition, Finishing Position Points, Tournament Type, Tournament Name, FirstName, LastName
```

Run ingest (replace with your actual file path):
```bash
backend/.venv/bin/python backend/ingestion/ingest_simple.py "/absolute/path/YourFile.xlsx"
```

This writes Players, Events, Results, and computed Rankings to DynamoDB Local.

---

## 7) Run the API

```bash
backend/.venv/bin/uvicorn backend.api.main:app --reload --port 8008
```

Test in another terminal:
```bash
curl http://127.0.0.1:8008/health
```

---

## 8) Run the UI

```bash
cd frontend
npm install
echo "VITE_API_BASE=http://localhost:8008" > .env.development
npm run dev
# open http://localhost:5173/
```

---

## 9) One-liner quick start (macOS)

```bash
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
```

---


## Useful commands

```bash
# list DynamoDB tables (Local) — requires AWS CLI
aws dynamodb list-tables --endpoint-url http://localhost:8000 --region us-east-1

# delete all local tables (careful)
for t in $(aws dynamodb list-tables --endpoint-url http://localhost:8000 --query 'TableNames[]' --output text); do
  aws dynamodb delete-table --table-name "$t" --endpoint-url http://localhost:8000
done
```

> Keep real spreadsheets out of git. Add `*.xlsx` to `.gitignore`.
