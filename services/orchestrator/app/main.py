import os
from datetime import datetime,timezone

import botocore
import boto3
import psycopg2
from psycopg2.extras import Json as psycopg_json
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

    with get_pg_conn() as conn:
        with conn.cursor() as cur:
            # Finding pipepline_id
            cur.execute("select id from agent.pipelines where name = %s;", (evt.pipeline_name,))
            row = cur.fetchone()
            if row is None:
                raise RuntimeError(f"Unknown pipeline: {evt.pipeline_name}")
            pipeline_id = row[0]

            # Create incident
            cur.execute(
                """
                insert into agent.incidents(pipeline_id, event_type, payload_json, detected_at, status)
                values (%s, %s, %s::jsonb, %s, 'OPEN')
                returning incident_id;
                """,
                (pipeline_id, evt.event_type, psycopg_json(evt.payload), ts),
            )
            incident_id = cur.fetchone()[0]

        conn.commit()

    return {"accepted": True, "incident_id": incident_id}
    # Saving only an audit row in smoke_test to prove end-to-end DB write
    # with get_pg_conn() as conn:
    #     with conn.cursor() as cur:
    #         cur.execute(
    #             "insert into agent.smoke_test(note) values (%s) returning id;",
    #             (f"incident:{evt.pipeline_name}:{evt.event_type}:{ts.isoformat()}",),
    #         )
    #         new_id = cur.fetchone()[0]
    #     conn.commit()
    # not using anymore as audit work is done.
    # return {"accepted": True, "audit_id": new_id}

@app.get("/incidents")
def list_indents(limit: int = 20) -> list[dict]:
    """
    Function to extract number of incidents that have been recorded.
    These incidents can be from any pipeline.

    Args:
        limit (int) : Limit number for extracting results from database. Defaults to 20.

    Returns:
        list[dict]: Returns a list of dictionary containing incident_id, name of the pipeline
            type of error/event, status of the error/event and the time it was detected. Ordered
            by detection time
    """

    with get_pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select i.incident_id, p.name, i.event_type, i.status, i.detected_at
                from incidents i
                join agent.pipelines p on p.id = i.pipeline_id
                order by i.detected_at desc
                limit %s;
                """,
                (limit,),
            )
            rows = cur.fetchall()

    return [
        {
            "incident_id": r[0],
            "pipeline": r[1],
            "event_type": r[2],
            "status": r[3],
            "detected_at": r[4],
        }
        for r in rows
    ]
