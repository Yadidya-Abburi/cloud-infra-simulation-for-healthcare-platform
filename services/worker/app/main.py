import os
import sys
import json
import time
import socket
import logging
import requests
import redis
import psycopg2
from psycopg2.extras import RealDictCursor
from prometheus_client import Counter, Gauge, Histogram, start_http_server

worker_id = os.getenv("WORKER_ID", socket.gethostname())

logging.basicConfig(
    level=logging.INFO,
    format='{"time": "%(asctime)s", "service": "worker", "worker_id": "' + worker_id + '", "level": "%(levelname)s", "message": "%(message)s"}'
)
logger = logging.getLogger("worker")

# Metrics
JOBS_PROCESSED_TOTAL = Counter(
    "worker_jobs_processed_total",
    "Total jobs successfully completed by background worker",
    ["worker_id", "job_type"]
)
JOBS_FAILED_TOTAL = Counter(
    "worker_jobs_failed_total",
    "Total jobs failed during worker processing",
    ["worker_id", "job_type", "reason"]
)
JOB_PROCESSING_LATENCY = Histogram(
    "worker_job_duration_seconds",
    "Time taken to process a single job in seconds",
    ["job_type"]
)
QUEUE_DEPTH = Gauge("worker_queue_depth", "Current queue depth observed by worker")
WORKER_ACTIVE = Gauge("worker_status", "Worker operational status (1=active, 0=inactive)", ["worker_id"])

# Configuration
DB_HOST = os.getenv("DB_HOST", "postgres")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "healthcare")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres_secret")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
EHR_SERVICE_URL = os.getenv("EHR_SERVICE_URL", "http://mock-ehr:8083")
METRICS_PORT = int(os.getenv("METRICS_PORT", "9100"))

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        connect_timeout=5
    )

def get_redis_client():
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, socket_timeout=5)

def update_job_status(job_id: str, status: str, result: dict = None, error_message: str = None, retry_count: int = 0):
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE jobs
                SET status = %s,
                    result = %s,
                    error_message = %s,
                    retry_count = %s,
                    updated_at = NOW()
                WHERE id = %s;
                """,
                (status, json.dumps(result) if result else None, error_message, retry_count, job_id)
            )
            # Log audit event
            cur.execute(
                """
                INSERT INTO audit_logs (event_type, source_service, details)
                VALUES (%s, %s, %s);
                """,
                (f"job_{status}", f"worker-{worker_id}", json.dumps({"job_id": job_id, "error": error_message}))
            )
            conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to update database for job {job_id}: {str(e)}")

def process_job(job_data: dict, r: redis.Redis):
    job_id = job_data.get("job_id")
    patient_id = job_data.get("patient_id")
    job_type = job_data.get("job_type", "ehr_sync")
    retry_count = job_data.get("retry_count", 0)
    max_retries = 3

    logger.info(f"Picked up job={job_id} patient={patient_id} (attempt {retry_count + 1})")
    update_job_status(job_id, "processing", retry_count=retry_count)

    start_time = time.time()
    try:
        # Step 1: Call Mock EHR Service
        ehr_resp = requests.post(
            f"{EHR_SERVICE_URL}/api/v1/patients/sync",
            json={"patient_id": patient_id},
            timeout=4.0
        )
        if ehr_resp.status_code != 200:
            raise Exception(f"EHR Service rejected sync with HTTP {ehr_resp.status_code}: {ehr_resp.text}")

        ehr_data = ehr_resp.json()

        # Step 2: Mark Success
        elapsed = time.time() - start_time
        JOB_PROCESSING_LATENCY.labels(job_type=job_type).observe(elapsed)
        JOBS_PROCESSED_TOTAL.labels(worker_id=worker_id, job_type=job_type).inc()

        result_payload = {
            "processed_by": worker_id,
            "latency_seconds": round(elapsed, 3),
            "ehr_sync": ehr_data
        }
        update_job_status(job_id, "completed", result=result_payload, retry_count=retry_count)
        logger.info(f"Successfully finished job={job_id} in {round(elapsed, 2)}s")

    except Exception as e:
        elapsed = time.time() - start_time
        err_str = str(e)
        logger.error(f"Error processing job={job_id}: {err_str}")

        if retry_count < max_retries:
            # Re-enqueue for retry with backoff
            retry_count += 1
            job_data["retry_count"] = retry_count
            r.rpush("healthcare:jobs:queue", json.dumps(job_data))
            update_job_status(job_id, "retrying", error_message=err_str, retry_count=retry_count)
            JOBS_FAILED_TOTAL.labels(worker_id=worker_id, job_type=job_type, reason="retried").inc()
            logger.warning(f"Re-enqueued job={job_id} for retry #{retry_count}")
        else:
            # Exceeded max retries -> permanent failure (DLQ)
            update_job_status(job_id, "failed", error_message=f"Exceeded max retries. Last error: {err_str}", retry_count=retry_count)
            JOBS_FAILED_TOTAL.labels(worker_id=worker_id, job_type=job_type, reason="max_retries_exceeded").inc()
            logger.critical(f"Job={job_id} marked DEAD after {max_retries} failed attempts")

def main():
    logger.info(f"Starting worker daemon (worker_id={worker_id})...")
    # Start Prometheus metrics server
    try:
        start_http_server(METRICS_PORT)
        logger.info(f"Prometheus metrics server active on port {METRICS_PORT}")
    except Exception as e:
        logger.error(f"Failed to start Prometheus metrics server: {e}")

    WORKER_ACTIVE.labels(worker_id=worker_id).set(1)

    # Wait for Redis and DB to become reachable
    while True:
        try:
            r = get_redis_client()
            r.ping()
            conn = get_db_connection()
            conn.close()
            logger.info("Dependencies verified. Worker entering dispatch loop.")
            break
        except Exception as e:
            logger.warning(f"Waiting for dependencies: {e}")
            time.sleep(2)

    while True:
        try:
            # Gauge current queue depth
            q_len = r.llen("healthcare:jobs:queue")
            QUEUE_DEPTH.set(q_len)

            # Blocking pop from Redis (timeout 2s)
            item = r.blpop("healthcare:jobs:queue", timeout=2)
            if item:
                _, payload_bytes = item
                job_data = json.loads(payload_bytes.decode("utf-8"))
                process_job(job_data, r)
        except redis.exceptions.ConnectionError:
            logger.error("Redis connection lost. Reconnecting in 3s...")
            time.sleep(3)
        except Exception as e:
            logger.error(f"Unexpected worker loop exception: {e}")
            time.sleep(1)

if __name__ == "__main__":
    main()
