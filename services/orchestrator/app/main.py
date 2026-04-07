import os
from datetime import datetime,timezone

import botocore
import boto3
import psycopg2
from fastapi import FastAPI
from pydantic import BaseModel

# Extracting value from .env variables
def _env(name: str, default: str | None = None) -> str:
    """
    Take environment variable names as input and find value for it or returns default value
    if the variable is not present in the environment
    Raises runtime error if default is also missing.

    Args:
        name (str): Name of the enviroment variable to extract value
        default (str): Default value to be used if the environment variable is not present.

    Return:
        str: Value of the environment variable from the os/docker etc.
    """
    v = os.getenv(name,default)

    if v is None or v =="":
        raise RuntimeError(f"Missing required env var: {name}")

    return v

# Setting up PostgreSQL Connection
def get_pg_conn() -> psycopg2.extensions.connection:
    """
    Wrapper function for connecting with PostgreSQL database.

    Args:
        None

    Returns:
        psycopg2.extensions.connection: Connection instance for PostgreSQL database
    """
    host = _env("POSTGRES_HOST")
    port = _env("POSTGRES_PORT")
    db = _env("POSTGRES_DB")
    user = _env("POSTGRES_USER")
    pwd = _env("POSTGRES_PASSWORD")

    return psycopg2.connect(host=host, port=port, dbname=db, user=user, password=pwd)

# Setting up S3 connection
def get_s3_client() -> botocore.client.BaseClient:
    """
    Wrapper function for connecting with S3.

    Args:
        None

    Returns:
        botocore.client.BaseClient: Connection/client instance for S3.
    """

    endpoint = _env("MINIO_ENDPOINT")
    access = _env("MINIO_ACCESS_KEY")
    secret = _env("MINIO_SECRET_KEY")
    region = _env("MINIO_REGION")

    return boto3.client(
        "s3",
        endpoint_url=f"http://{endpoint}",
        aws_access_key_id = access,
        aws_secret_access_key = secret,
        region_name = region
    )

# Defining base pydanctic class for Incidents.
class IncidentEvent(BaseModel):
    pipeline_name: str
    event_type: str
    payload: dict = {}
    timestamp: datetime | None = None

# Setting up FastAPI based orchestrator
app = FastAPI(title = "Self-Healing Orchestrator", version="0.1.0")

@app.get("/health")
def health() -> dict:
    """
    Wrapper function to perform health checks for PostgreSQL and S3.

    Args:
        None

    Returns:
        dict: Dictionary containing detailed information of PostgreSQL and S3 health checks.
    """

    # PostgreSQL check
    pg_ok = False
    pg_error = None
    try:
        with get_pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("select 1;")
                _ = cur.fetchone()
        pg_ok = True
    except Exception as e:
        pg_error = str(e)

    # Minio/S3 check
    s3_ok = False
    s3_error = None
    try:
        s3 = get_s3_client()
        _ = s3.list_buckets()
        s3_ok = True
    except Exception as e:
        s3_error = str(e)

    status = "ok" if (pg_ok and s3_ok) else "degraded"
    return {
        "status": status,
        "postgres": {"ok": pg_ok, "error": pg_error},
        "minio": {"ok": s3_ok, "error": s3_error},
        "time_utc": datetime.now(timezone.utc).isoformat()
    }

@app.post("/events/incident")
def create_incident(evt: IncidentEvent) -> dict:
    """
    Funtion to save incidents that have happened in to PostgreSQL.

    Args:
        evt (IncidentEvent): Event instances crossed checked against pydantic class

    Returns:
        dict: Returns a dictionary contaiing information whether the even was saved or not.
    """

    ts = evt.timestamp or datetime.now(timezone.utc)

    # Saving only an audit row in smoke_test to prove end-to-end DB write
    with get_pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "insert into agent.smoke_test(note) values (%s) returning id;",
                (f"incident:{evt.pipeline_name}:{evt.event_type}:{ts.isoformat()}",),
            )
            new_id = cur.fetchone()[0]
        conn.commit()

    return {"accepted": True, "audit_id": new_id}
