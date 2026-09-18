import os
import json
import time
import uuid
import logging
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Response, status, Request
from pydantic import BaseModel
import redis
import psycopg2
from psycopg2.extras import RealDictCursor
import requests
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

logging.basicConfig(
    level=logging.INFO,
    format='{"time": "%(asctime)s", "service": "api-service", "version": "' + os.getenv("APP_VERSION", "v1.0.0") + '", "level": "%(levelname)s", "message": "%(message)s"}'
)
logger = logging.getLogger("api-service")

app = FastAPI(title="Healthcare Platform API", version=os.getenv("APP_VERSION", "v1.0.0"))

# Metrics
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests handled by API",
    ["method", "endpoint", "status"]
)
HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"]
)
DB_CONNECTED = Gauge("api_db_connected", "Database connection status (1=healthy, 0=unhealthy)")
REDIS_CONNECTED = Gauge("api_redis_connected", "Redis connection status (1=healthy, 0=unhealthy)")

# Config
DB_HOST = os.getenv("DB_HOST", "postgres")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "healthcare")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres_secret")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "http://ai-service:8082")

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        connect_timeout=3
    )

def get_redis_client():
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, socket_timeout=3)

# Data Models
class JobCreateRequest(BaseModel):
    patient_id: str
    job_type: str = "ehr_sync"
    payload: Optional[Dict[str, Any]] = None

class DiagnoseRequest(BaseModel):
    patient_id: str
    symptoms: List[str]

@app.middleware("http")
async def monitor_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    
    # Avoid recording /metrics in high frequency metrics
    if request.url.path not in ["/metrics"]:
        endpoint = request.url.path
        HTTP_REQUESTS_TOTAL.labels(method=request.method, endpoint=endpoint, status=response.status_code).inc()
        HTTP_REQUEST_DURATION.labels(method=request.method, endpoint=endpoint).observe(duration)
        
    return response

@app.get("/health")
def liveness():
    """Liveness probe: verifies container process is up."""
    return {
        "status": "healthy",
        "service": "api",
        "version": os.getenv("APP_VERSION", "v1.0.0"),
        "color": os.getenv("DEPLOYMENT_COLOR", "blue")
    }

@app.get("/ready")
def readiness():
    """Readiness probe: verifies backing dependencies (PostgreSQL & Redis)."""
    db_ok = False
    redis_ok = False
    errors = []

    # Check DB
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
        conn.close()
        db_ok = True
        DB_CONNECTED.set(1)
    except Exception as e:
        DB_CONNECTED.set(0)
        errors.append(f"DB Error: {str(e)}")

    # Check Redis
    try:
        r = get_redis_client()
        r.ping()
        redis_ok = True
        REDIS_CONNECTED.set(1)
    except Exception as e:
        REDIS_CONNECTED.set(0)
        errors.append(f"Redis Error: {str(e)}")

    if not (db_ok and redis_ok):
        logger.warning(f"Readiness check failed: {errors}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"ready": False, "errors": errors}
        )

    return {
        "ready": True,
        "database": "connected",
        "redis": "connected",
        "version": os.getenv("APP_VERSION", "v1.0.0"),
        "color": os.getenv("DEPLOYMENT_COLOR", "blue")
    }

@app.get("/api/v1/patients")
def list_patients():
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, mrn, first_name, last_name, date_of_birth, gender FROM patients ORDER BY created_at DESC;")
            rows = cur.fetchall()
        conn.close()
        return {"count": len(rows), "patients": rows}
    except Exception as e:
        logger.error(f"Failed to fetch patients: {str(e)}")
        raise HTTPException(status_code=500, detail="Database query error")

@app.post("/api/v1/jobs")
def submit_job(job_req: JobCreateRequest):
    job_id = f"job-{uuid.uuid4().hex[:8]}"
    created_at = time.time()
    
    # 1. Store in Database
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO jobs (id, patient_id, job_type, status, payload, created_at)
                VALUES (%s, %s, %s, %s, %s, NOW());
                """,
                (job_id, job_req.patient_id, job_req.job_type, "queued", json.dumps(job_req.payload or {}))
            )
            conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to save job {job_id} to DB: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    # 2. Push to Redis Queue
    try:
        r = get_redis_client()
        queue_payload = {
            "job_id": job_id,
            "patient_id": job_req.patient_id,
            "job_type": job_req.job_type,
            "payload": job_req.payload or {},
            "submitted_at": created_at
        }
        r.rpush("healthcare:jobs:queue", json.dumps(queue_payload))
        logger.info(f"Queued job={job_id} for patient={job_req.patient_id}")
    except Exception as e:
        logger.error(f"Failed to enqueue job {job_id} to Redis: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Queue error: {str(e)}")

    return {
        "job_id": job_id,
        "status": "queued",
        "patient_id": job_req.patient_id,
        "job_type": job_req.job_type
    }

@app.get("/api/v1/jobs/{job_id}")
def get_job_status(job_id: str):
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, patient_id, job_type, status, payload, result, retry_count, error_message, created_at, updated_at FROM jobs WHERE id = %s;", (job_id,))
            row = cur.fetchone()
        conn.close()
        if not row:
            raise HTTPException(status_code=404, detail="Job not found")
        return row
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve job {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/diagnose")
def trigger_ai_diagnosis(req: DiagnoseRequest):
    """Interacts with internal AI microservice privately over docker network."""
    try:
        resp = requests.post(
            f"{AI_SERVICE_URL}/generate",
            json={"patient_id": req.patient_id, "symptoms": req.symptoms},
            timeout=5.0
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=f"AI Service error: {resp.text}")
        return resp.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to contact AI service: {str(e)}")
        raise HTTPException(status_code=503, detail="AI Service is unreachable")

@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
