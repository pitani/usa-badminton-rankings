# create_tables.py  (safe for DynamoDB Local + AWS)
import os, sys
import boto3, botocore
from botocore.config import Config
from urllib.parse import urlparse

# ---- Endpoint & environment ----
ENDPOINT = os.getenv("DDB_ENDPOINT", "http://localhost:8000")
REGION   = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

parsed   = urlparse(ENDPOINT)
IS_LOCAL = parsed.hostname in ("localhost", "127.0.0.1")

cfg = Config(
    retries={"max_attempts": 3, "mode": "standard"},
    connect_timeout=3,
    read_timeout=5,
)

session  = boto3.Session(region_name=REGION)
client   = session.client("dynamodb", endpoint_url=ENDPOINT, config=cfg)
dynamodb = session.resource("dynamodb", endpoint_url=ENDPOINT, config=cfg)

def ping():
    try:
        client.list_tables()
        return True
    except Exception as e:
        print(f"Cannot reach DynamoDB at {ENDPOINT}: {type(e).__name__}: {e}", file=sys.stderr)
        print("   - Is Docker running?")
        print("   - Is the 'dynamodb-local' container up and listening on this port?")
        print("   - If you used a different host port, export DDB_ENDPOINT=http://localhost:<port>", file=sys.stderr)
        sys.exit(1)

def exists(name):
    try:
        client.describe_table(TableName=name)
        return True
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            return False
        raise

def create_players():
    name = "Players"
    if exists(name): return print(f"{name} exists")
    client.create_table(
        TableName=name, BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[{"AttributeName":"PlayerID","AttributeType":"N"}],
        KeySchema=[{"AttributeName":"PlayerID","KeyType":"HASH"}],
    )
    client.get_waiter("table_exists").wait(TableName=name)
    print(f"Created {name}")

def create_events():
    name = "Events"
    if exists(name): return print(f"{name} exists")
    client.create_table(
        TableName=name, BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[{"AttributeName":"EventCode","AttributeType":"S"}],
        KeySchema=[{"AttributeName":"EventCode","KeyType":"HASH"}],
    )
    client.get_waiter("table_exists").wait(TableName=name)
    print(f"Created {name}")

def create_results():
    name = "Results"
    if exists(name): return print(f"{name} exists")
    client.create_table(
        TableName=name, BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[
            {"AttributeName":"PlayerEvent","AttributeType":"S"},
            {"AttributeName":"TournamentName","AttributeType":"S"},
            {"AttributeName":"PlayerID","AttributeType":"N"},
            {"AttributeName":"EventCode","AttributeType":"S"},
        ],
        KeySchema=[
            {"AttributeName":"PlayerEvent","KeyType":"HASH"},
            {"AttributeName":"TournamentName","KeyType":"RANGE"},
        ],
        GlobalSecondaryIndexes=[{
            "IndexName":"GSI1-Player-Event",
            "KeySchema":[
                {"AttributeName":"PlayerID","KeyType":"HASH"},
                {"AttributeName":"EventCode","KeyType":"RANGE"},
            ],
            "Projection":{"ProjectionType":"ALL"}
        }],
    )
    client.get_waiter("table_exists").wait(TableName=name)
    print(f"Created {name}")

def create_rankings():
    name = "Rankings"
    if exists(name): return print(f"{name} exists")
    params = {
        "TableName": name,
        "BillingMode": "PAY_PER_REQUEST",
        "AttributeDefinitions": [
            {"AttributeName":"EventCode","AttributeType":"S"},
            {"AttributeName":"Rank","AttributeType":"N"},
        ],
        "KeySchema": [
            {"AttributeName":"EventCode","KeyType":"HASH"},
            {"AttributeName":"Rank","KeyType":"RANGE"},
        ],
    }
    # PITR is AWS-only; DynamoDB Local will reject it
    if not IS_LOCAL:
        params["PointInTimeRecoverySpecification"] = {"PointInTimeRecoveryEnabled": True}

    client.create_table(**params)
    client.get_waiter("table_exists").wait(TableName=name)
    print(f"Created {name}")

def create_ingestion_audit():
    name = "IngestionAudit"
    if exists(name): return print(f"{name} exists")
    client.create_table(
        TableName=name, BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[{"AttributeName":"ObjectKey","AttributeType":"S"}],
        KeySchema=[{"AttributeName":"ObjectKey","KeyType":"HASH"}],
    )
    client.get_waiter("table_exists").wait(TableName=name)
    print(f"Created {name}")
    # TTL works in Local (no-op enforcement), fine to set
    try:
        client.update_time_to_live(
            TableName=name,
            TimeToLiveSpecification={"Enabled": True, "AttributeName": "ExpireAt"}
        )
    except Exception as e:
        print(f"TTL setup warning: {e}")

if __name__ == "__main__":
    ping()
    create_players()
    create_events()
    create_results()
    create_rankings()
    create_ingestion_audit()
    print("All tables ready.")
