import os
import time
import random
import logging
from typing import Optional
from fastapi import FastAPI, HTTPException, Response, status
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

logging.basicConfig(
    level=logging.INFO,
    format='{"time": "%(asctime)s", "service": "mock-ehr", "level": "%(levelname)s", "message": "%(message)s"}'
)
logger = logging.getLogger("mock-ehr")

app = FastAPI(title="Mock External EHR Service", version="1.0.0")

# Metrics
EHR_REQUESTS_TOTAL = Counter(
    "ehr_requests_total",
    "Total EHR requests received",
    ["endpoint", "status"]
)
EHR_REQUEST_LATENCY = Histogram(
    "ehr_request_duration_seconds",
    "EHR request latency in seconds",
    ["endpoint"]
)

class EHRSyncRequest(BaseModel):
    patient_id: str
    mrn: Optional[str] = "MRN-1001"
    data_type: Optional[str] = "vitals"

class EHRModeUpdate(BaseModel):
    mode: str

def get_current_mode() -> str:
    return os.getenv("EHR_MODE", "normal").lower()

@app.get("/health")
def health():
    mode = get_current_mode()
    if mode == "unavailable":
        raise HTTPException(status_code=503, detail="EHR Service is currently unavailable")
    return {"status": "healthy", "service": "mock-ehr", "mode": mode}

@app.get("/mode")
def get_mode():
    return {"mode": get_current_mode()}

@app.post("/mode")
def set_mode(payload: EHRModeUpdate):
    valid_modes = ["normal", "slow", "timeout", "error_500", "auth_error", "unavailable"]
    if payload.mode not in valid_modes:
        raise HTTPException(status_code=400, detail=f"Invalid mode. Valid: {valid_modes}")
    os.environ["EHR_MODE"] = payload.mode
    logger.info(f"EHR simulation mode changed to: {payload.mode}")
    return {"message": "Mode updated successfully", "current_mode": payload.mode}

@app.post("/api/v1/patients/sync")
def sync_patient(payload: EHRSyncRequest):
    start_time = time.time()
    mode = get_current_mode()
    logger.info(f"Received sync request for patient={payload.patient_id}, current_mode={mode}")

    try:
        if mode == "unavailable":
            EHR_REQUESTS_TOTAL.labels(endpoint="sync_patient", status="503").inc()
            raise HTTPException(status_code=503, detail="EHR Gateway is down")

        elif mode == "auth_error":
            EHR_REQUESTS_TOTAL.labels(endpoint="sync_patient", status="401").inc()
            raise HTTPException(status_code=401, detail="EHR API Token expired or unauthorized")

        elif mode == "error_500":
            EHR_REQUESTS_TOTAL.labels(endpoint="sync_patient", status="500").inc()
            raise HTTPException(status_code=500, detail="Internal Server Error in Hospital EHR provider")

        elif mode == "timeout":
            # Simulate upstream network/gateway timeout (> 10s)
            time.sleep(6.0)
            EHR_REQUESTS_TOTAL.labels(endpoint="sync_patient", status="504").inc()
            raise HTTPException(status_code=504, detail="Upstream EHR Gateway timeout")

        elif mode == "slow":
            # Inject degraded performance latency (2 to 4 seconds)
            time.sleep(2.5)

        # Normal operation
        latency = time.time() - start_time
        EHR_REQUEST_LATENCY.labels(endpoint="sync_patient").observe(latency)
        EHR_REQUESTS_TOTAL.labels(endpoint="sync_patient", status="200").inc()

        return {
            "status": "synchronized",
            "patient_id": payload.patient_id,
            "mrn": payload.mrn,
            "external_record_id": f"EXT-EHR-{random.randint(100000, 999999)}",
            "sync_timestamp": time.time(),
            "mode": mode
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        EHR_REQUESTS_TOTAL.labels(endpoint="sync_patient", status="500").inc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
