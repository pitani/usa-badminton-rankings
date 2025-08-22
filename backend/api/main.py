from __future__ import annotations

import os
from decimal import Decimal
from typing import Any, Dict, Iterable, List

import boto3
from botocore.config import Config
from boto3.dynamodb.conditions import Key
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

# ---------------------------
# DynamoDB wiring (Local or AWS)
# ---------------------------

DDB_ENDPOINT = os.getenv("DDB_ENDPOINT")  # e.g., "http://localhost:8000" for DynamoDB Local
REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

def ddb_resource():
    cfg = Config(retries={"max_attempts": 5, "mode": "standard"}, connect_timeout=3, read_timeout=10)
    if DDB_ENDPOINT:
        session = boto3.Session(
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", "dummy"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", "dummy"),
            region_name=REGION,
        )
        return session.resource("dynamodb", endpoint_url=DDB_ENDPOINT, config=cfg)
    return boto3.Session(region_name=REGION).resource("dynamodb", config=cfg)

ddb = ddb_resource()
T_EVENTS   = ddb.Table("Events")
T_RESULTS  = ddb.Table("Results")
T_RANKINGS = ddb.Table("Rankings")

# ---------------------------
# FastAPI + CORS
# ---------------------------

app = FastAPI(title="USAB Rankings (simple API)")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # keep wide-open for local dev; restrict in prod
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------
# Helpers
# ---------------------------

def dec_to_native(x: Any) -> Any:
    if isinstance(x, list):
        return [dec_to_native(i) for i in x]
    if isinstance(x, dict):
        return {k: dec_to_native(v) for k, v in x.items()}
    if isinstance(x, Decimal):
        return int(x) if x % 1 == 0 else float(x)
    return x

def query_all(table, **kwargs) -> Iterable[Dict[str, Any]]:
    lek = None
    while True:
        if lek:
            kwargs["ExclusiveStartKey"] = lek
        resp = table.query(**kwargs)
        for it in resp.get("Items", []):
            yield it
        lek = resp.get("LastEvaluatedKey")
        if not lek:
            break

def scan_all(table, **kwargs) -> Iterable[Dict[str, Any]]:
    lek = None
    while True:
        if lek:
            kwargs["ExclusiveStartKey"] = lek
        resp = table.scan(**kwargs)
        for it in resp.get("Items", []):
            yield it
        lek = resp.get("LastEvaluatedKey")
        if not lek:
            break

# ---------------------------
# Endpoints
# ---------------------------

@app.get("/health")
def health():
    return {"status": "ok", "backend": "local" if DDB_ENDPOINT else "aws", "region": REGION, "endpoint": DDB_ENDPOINT or "aws"}

@app.get("/events")
def list_events(limit: int = Query(500, ge=1, le=5000)):
    """Events is tiny; scan is fine."""
    items: List[Dict[str, Any]] = []
    for it in scan_all(T_EVENTS, ProjectionExpression="EventCode, Gender, Discipline, Age"):
        items.append(dec_to_native(it))
        if len(items) >= limit:
            break
    items.sort(key=lambda x: x.get("EventCode",""))
    return items

@app.get("/rankings")
def rankings_for_event(
    event: str = Query(..., description="EventCode, e.g. 'BS U17'"),
    limit: int = Query(50, ge=1, le=1000),
    start_rank: int = Query(1, ge=1, description="Start from this unique SK Rank"),
):
    """
    Returns rankings for an event with UNIQUE rank per row.
    """
    items: List[Dict[str, Any]] = []
    got = 0
    last = None

    while got < limit:
        params = {
            "KeyConditionExpression": Key("EventCode").eq(event) & Key("Rank").gte(start_rank),
            "Limit": min(100, limit - got),
        }
        if last:
            params["ExclusiveStartKey"] = last
        resp = T_RANKINGS.query(**params)
        batch = resp.get("Items", [])
        for it in batch:
            items.append(dec_to_native(it))
        got += len(batch)
        last = resp.get("LastEvaluatedKey")
        if not last or len(batch) == 0:
            break

    # Final stable sort to ensure: Rank asc, LastName asc, FirstName asc
    items.sort(key=lambda it: (it.get("Rank", 0), it.get("LastName",""), it.get("FirstName","")))

    next_start = (items[-1]["Rank"] + 1) if items else None
    return {"event": event, "count": len(items), "items": items, "next_start_rank": next_start}

@app.get("/events/{event}/export.csv")
def export_event_csv(event: str):
    """
    CSV export using UNIQUE rank (no duplicates).
    Columns: EventCode,Rank,PlayerID,FirstName,LastName,TotalPoints,Top1,Top2,Top3,Top4,CountedTournaments
    """
    def gen():
        yield b"EventCode,Rank,PlayerID,FirstName,LastName,TotalPoints,Top1,Top2,Top3,Top4,CountedTournaments\n"
        for it in query_all(T_RANKINGS, KeyConditionExpression=Key("EventCode").eq(event)):
            it = dec_to_native(it)
            vec = (it.get("SelectedTop4Vector") or [0,0,0,0])[:4]
            row = [
                it.get("EventCode",""),
                it.get("Rank",""),
                it.get("PlayerID",""),
                (it.get("FirstName","") or "").replace(",", " "),
                (it.get("LastName","") or "").replace(",", " "),
                it.get("TotalPoints",""),
                vec[0] if len(vec)>0 else 0,
                vec[1] if len(vec)>1 else 0,
                vec[2] if len(vec)>2 else 0,
                vec[3] if len(vec)>3 else 0,
                it.get("CountedTournaments",""),
            ]
            yield (",".join(map(str,row)) + "\n").encode("utf-8")

    fname = event.replace(" ", "_") + "_rankings.csv"
    return StreamingResponse(gen(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename=\"%s\"' % fname})

@app.get("/player-results")
def player_results(
    playerId: int = Query(..., description="Numeric PlayerID"),
    event: str = Query(..., description="EventCode, e.g. 'BS U17'"),
    limit: int = Query(200, ge=1, le=2000),
):
    """
    Raw tournament rows for (playerId, event).
    PK = f\"{playerId}#{event}\" ; SK = TournamentName (lexicographic)
    """
    pk = f"{playerId}#{event}"
    items: List[Dict[str, Any]] = []
    got = 0
    last = None

    while got < limit:
        params = {
            "KeyConditionExpression": Key("PlayerEvent").eq(pk),
            "Limit": min(100, limit - got),
            "ScanIndexForward": False,  # reverse by TournamentName
        }
        if last:
            params["ExclusiveStartKey"] = last
        resp = T_RESULTS.query(**params)
        batch = resp.get("Items", [])
        for it in batch:
            items.append(dec_to_native(it))
        got += len(batch)
        last = resp.get("LastEvaluatedKey")
        if not last or len(batch) == 0:
            break

    return {"count": len(items), "items": items}
