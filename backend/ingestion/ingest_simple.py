#!/usr/bin/env python3
# ingest_simple.py — minimal, no validations, no exceptions
# Excel columns expected exactly as:
#   PlayerID, Event Name, FinishingPosition, Finishing Position Points,
#   Tournament Type, Tournament Name, FirstName, LastName
#
# Core rules:
# - Player appears in age A only if they have ≥1 result in age A
# - Points for age A = top 4 from (A ∪ lower(A)) — NOT “own + carry”
# - Unique ranking: 1..N (no duplicate ranks)
# - Tie-breaks: total desc → per-slot vector desc → cnt desc → LastName → FirstName

import os, sys, re
from datetime import date, datetime
from decimal import Decimal
from collections import defaultdict

import pandas as pd
import boto3
from botocore.config import Config
from boto3.dynamodb.conditions import Key

# ---------- Config / Dynamo ----------
DDB_ENDPOINT = os.getenv("DDB_ENDPOINT")       # e.g. http://localhost:8000 for Local
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

def to_dec(x):
    if x is None: return None
    if isinstance(x, Decimal): return x
    if isinstance(x, (int, float)): return Decimal(str(x))
    s = str(x).strip()
    return Decimal(s) if s else None

# ---------- Helpers ----------
EVENT_RE = re.compile(r"^\s*([BGX])([SD]?)\s*U\s*(\d+)\s*$", re.IGNORECASE)

def parse_event(s: str):
    m = EVENT_RE.match(s) or EVENT_RE.match(s.replace(" ", ""))
    g, d, n = m.group(1).upper(), (m.group(2) or "").upper(), m.group(3)
    gender = "Boys" if g=="B" else ("Girls" if g=="G" else "Mixed")
    d = d if d else ("D" if g=="X" else "")
    discipline = {"S":"Singles","D":"Doubles"}.get(d, "Doubles" if g=="X" else None)
    age = f"U{n}"
    code = f"{g}{d} {age}".strip()
    return {"EventCode": code, "Gender": gender, "Discipline": discipline, "Age": age, "G": g, "D": d}

def lower_age(age: str):
    n = int(age[1:])
    return f"U{n-2}" if n > 11 else None

def pick_top4(points_list):
    pts_sorted = sorted([int(p) for p in points_list], reverse=True)[:4]
    while len(pts_sorted) < 4: pts_sorted.append(0)
    total = sum(pts_sorted[:4])
    cnt = len([p for p in pts_sorted if p > 0])
    return total, pts_sorted[:4], cnt

def disc_code(meta):
    return "XD" if meta["G"]=="X" else f"{meta['G']}{(meta['D'] or 'D')}"

# ---------- Main ----------
def ingest_and_rank(xlsx_path: str, as_of: date = None):
    if as_of is None: as_of = date.today()
    print(f"AS OF: {as_of.isoformat()}")

    # Read Excel (first sheet) and map your headers to internal names
    df = pd.read_excel(xlsx_path, sheet_name=0).rename(columns={
        "PlayerID": "PlayerID",
        "Event Name": "EventName",
        "FinishingPosition": "FinishingPosition",
        "Finishing Position Points": "PositionPoints",
        "Tournament Type": "TournamentType",
        "Tournament Name": "TournamentName",
        "FirstName": "FirstName",
        "LastName": "LastName",
    })

    # Trim strings
    for c in ["FirstName","LastName","EventName","TournamentName","TournamentType","FinishingPosition"]:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip()


    """df[["PlayerID","FirstName","LastName"]]
    → narrows the DataFrame to just the columns we need.

    .drop_duplicates()
    → if the same player appears in multiple rows (multiple tournaments), keep only one row per PlayerID so the dict has a single entry per player.

    .iterrows()
        → iterates over those unique rows.

    Dictionary comprehension:

    int(r["PlayerID"])                          # dict key: numeric PlayerID
    (
        str(r["FirstName"] or "").strip(),        # dict value: (FirstName, LastName)
        str(r["LastName"]  or "").strip()
    )


    casts PlayerID to int (so keys are integers)

    converts names to strings and trims whitespace (so "Alex " → "Alex")

    packs them into a tuple (FirstName, LastName) as the value """
    # Name cache
    name_by_pid = {
        int(r["PlayerID"]): (str(r["FirstName"] or "").strip(), str(r["LastName"] or "").strip())
        for _, r in df[["PlayerID","FirstName","LastName"]].drop_duplicates().iterrows()
    }

    # Tables
    d = ddb_resource()
    Players  = d.Table("Players")
    Events   = d.Table("Events")
    Results  = d.Table("Results")
    Rankings = d.Table("Rankings")

    # 1) Players
    with Players.batch_writer() as bw:
        for pid, grp in df.groupby("PlayerID"):
            pid_i = int(pid)
            fn = str(grp.iloc[0]["FirstName"] or "")
            ln = str(grp.iloc[0]["LastName"] or "")
            bw.put_item(Item={"PlayerID": to_dec(pid_i), "FirstName": fn, "LastName": ln})
    print("Players upserted.")

    # 2) Events
    seen = set()
    with Events.batch_writer() as bw:
        for ev_raw in df["EventName"].dropna().unique():
            meta = parse_event(str(ev_raw))
            code = meta["EventCode"]
            if code in seen: continue
            bw.put_item(Item={
                "EventCode": code,
                "Gender": meta["Gender"],
                "Discipline": meta["Discipline"],
                "Age": meta["Age"],
            })
            seen.add(code)
    print("Events upserted.")

    # 3) Results (all rows considered "in window")
    with Results.batch_writer() as bw:
        for _, r in df.iterrows():
            pid = int(r["PlayerID"])
            meta = parse_event(str(r["EventName"]))
            code = meta["EventCode"]
            pe = f"{pid}#{code}"
            tn = str(r["TournamentName"] or "").strip()
            if not tn: continue
            bw.put_item(Item={
                "PlayerEvent": pe,                 # PK
                "TournamentName": tn,              # SK
                "PlayerID": to_dec(pid),
                "EventCode": code,
                "TournamentType": str(r.get("TournamentType","") or ""),
                "FinishingPosition": str(r.get("FinishingPosition","") or ""),
                "PositionPoints": to_dec(r.get("PositionPoints")),
                "FirstName": name_by_pid.get(pid, ("",""))[0],
                "LastName":  name_by_pid.get(pid, ("",""))[1],
            })
    print("Results written.")

    # 4) Build point pools (all rows)
    # pts_by_age[(pid, disc)]["U17"] = [points, ...]
    pts_by_age = defaultdict(lambda: defaultdict(list))
    for _, r in df.iterrows():
        pid = int(r["PlayerID"])
        meta = parse_event(str(r["EventName"]))
        dc = disc_code(meta)
        age = meta["Age"]
        pts = float(r.get("PositionPoints") or 0)
        pts_by_age[(pid, dc)][age].append(pts)

    # 5) Compute + write Rankings per event
    ev_rows = df[["EventName"]].dropna().drop_duplicates()
    for _, row in ev_rows.iterrows():
        meta = parse_event(str(row["EventName"]))
        code, age, dc = meta["EventCode"], meta["Age"], disc_code(meta)
        low = lower_age(age)

        # candidates (eligibility: must have ≥1 result in target age)
        cand = []
        for (pid, dcode), by_age in pts_by_age.items():
            if dcode != dc: continue
            if age not in by_age or len(by_age[age]) == 0: continue
            pool = list(by_age[age])
            if low and low in by_age: pool.extend(by_age[low])
            total, vec, cnt4 = pick_top4(pool)
            fn, ln = name_by_pid.get(pid, ("",""))
            cand.append({"pid": pid, "fn": fn, "ln": ln, "total": total, "vec": vec, "cnt": cnt4})

        # ordering with tie-breaks — include LastName/FirstName to break final ties
        cand.sort(key=lambda r: (
            -r["total"],
            -r["vec"][0], -r["vec"][1], -r["vec"][2], -r["vec"][3],
            -r["cnt"],
            r["ln"],       # <- break ties by LastName
            r["fn"],       # <- then FirstName
        ))

        # delete old partition (paginate)
        lek = None
        while True:
            q = {"KeyConditionExpression": Key("EventCode").eq(code)}
            if lek: q["ExclusiveStartKey"] = lek
            resp = Rankings.query(**q)
            for it in resp.get("Items", []):
                Rankings.delete_item(Key={"EventCode": code, "Rank": it["Rank"]})
            lek = resp.get("LastEvaluatedKey")
            if not lek: break

        # write new ranks — UNIQUE (1..N) following the above order
        rank_items = []
        seq = 0
        for r in cand:
            seq += 1
            rank_items.append({
                "EventCode": code,
                "Rank": seq,                         # unique SK
                "PlayerID": to_dec(r["pid"]),
                "FirstName": r["fn"],
                "LastName": r["ln"],
                "TotalPoints": to_dec(r["total"]),
                "SelectedTop4Vector": [to_dec(x) for x in r["vec"]],
                "MostRecentDate": None,              # no dates in this pipeline
                "CountedTournaments": r["cnt"],
            })

        with Rankings.batch_writer() as bw:
            for it in rank_items:
                bw.put_item(Item=it)

        print(f"{code}: wrote {len(rank_items)} rows")

    print("Done.")

# ---------- CLI ----------
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python backend/ingestion/ingest_simple.py /absolute/path/file.xlsx [YYYY-MM-DD]")
    else:
        xlsx = sys.argv[1]
        as_of = datetime.strptime(sys.argv[2], "%Y-%m-%d").date() if len(sys.argv) >= 3 else None
        ingest_and_rank(xlsx, as_of)
