import os
import time
import random
import logging
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

logging.basicConfig(
    level=logging.INFO,
    format='{"time": "%(asctime)s", "service": "ai-service", "level": "%(levelname)s", "message": "%(message)s"}'
)
logger = logging.getLogger("ai-service")

app = FastAPI(title="Internal AI & Agent Diagnostics Service", version="1.0.0")

AI_REQUESTS_TOTAL = Counter(
    "ai_requests_total",
    "Total inference requests handled by AI service",
    ["model", "status"]
)
AI_INFERENCE_LATENCY = Histogram(
    "ai_inference_duration_seconds",
    "AI Inference processing latency in seconds",
    ["model"]
)

class DiagnosticPrompt(BaseModel):
    patient_id: str
    symptoms: List[str]
    model: Optional[str] = "clinical-bert-v2"

@app.get("/health")
def health():
    return {"status": "healthy", "service": "ai-service", "role": "internal-compute"}

@app.post("/generate")
def generate_diagnosis(payload: DiagnosticPrompt):
    start_time = time.time()
    logger.info(f"Processing AI inference for patient={payload.patient_id} with model={payload.model}")
    
    # Simulate non-trivial neural compute latency (150ms - 400ms)
    time.sleep(random.uniform(0.15, 0.40))
    
    # Mock AI response based on symptoms
    insights = [
        f"Detected elevated risk factors based on symptom count ({len(payload.symptoms)}).",
        "Recommended action: Order comprehensive metabolic panel and schedule follow-up.",
        "Differential diagnosis confidence: 94.2%"
    ]
    
    duration = time.time() - start_time
    AI_INFERENCE_LATENCY.labels(model=payload.model).observe(duration)
    AI_REQUESTS_TOTAL.labels(model=payload.model, status="200").inc()
    
    return {
        "patient_id": payload.patient_id,
        "model": payload.model,
        "inference_duration_sec": round(duration, 3),
        "insights": insights,
        "confidence_score": 0.942,
        "timestamp": time.time()
    }

@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
