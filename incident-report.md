# Incident Post-Mortem Report: Production Simulation

**Incident Reference:** INC-2026-09-01  
**Severity:** P2 (Major Degradation - Upstream EHR Gateway Outage & Retry Backpressure)  
**Platform Domain:** EHR Data Synchronization & Asynchronous Background Processing  
**Status:** Resolved  
**Incident Commander / On-Call Engineer:** Cloud Operations Team  

---

## 1. Executive Summary
On 2026-09-18 at 15:35 UTC, the simulated external Electronic Health Record (EHR) partner gateway suffered an unannounced internal service degradation, returning HTTP 500 error responses to all outbound patient vitals synchronization requests.

The healthcare platform's automated observability plane detected the failure within 10 seconds via Prometheus alert rule `EHRFailureRateHigh`. The decoupled asynchronous background worker architecture prevented API ingress outages: incoming patient appointments and diagnoses continued to be ingested with zero dropped requests.

Background workers engaged automated exponential backoff retry cycles. Upon restoration of the external EHR dependency, queued synchronization jobs self-healed, drained within 2.1 seconds, and all Prometheus alert states returned to normal.

---

## 2. Incident Timeline

| Timestamp (UTC) | Operational Event & Lifecycle Stage | Technical Evidence / Observation |
|---|---|---|
| **15:35:00** | **Failure Occurs** | Partner EHR gateway changes state to `error_500`. Sync requests fail immediately. |
| **15:35:10** | **Detection** | Prometheus evaluates `rate(ehr_requests_total{status=~"5.."}[1m]) > 0`. Alert `EHRFailureRateHigh` transitions to `FIRING`. |
| **15:35:12** | **Investigation** | On-call engineer checks Grafana Operational Overview dashboard. Worker logs show: `EHR Service rejected sync with HTTP 500: Internal Server Error`. |
| **15:35:18** | **Root Cause Confirmed** | Partner EHR `/health` confirms mode degradation. Database connection and Redis queues verified fully healthy. |
| **15:35:22** | **Mitigation / Recovery** | Partner EHR restored to `normal` mode. Workers resume processing. |
| **15:35:24** | **Verification** | 5 retrying jobs complete successfully in 0.045s. Redis queue depth drains to 0. |
| **15:35:35** | **Alert Resolution** | Prometheus clears alert `EHRFailureRateHigh`. System fully stable. |

---

## 3. Impact Assessment

* **Ingress API Availability**: **100% Uptime**. Due to asynchronous queue decoupling via Redis, public API endpoints (`/api/v1/patients`, `/api/v1/jobs`) remained fully responsive without 504 gateway timeouts.
* **Data Loss**: **0 Records Lost**. Every sync job was persisted in PostgreSQL and re-enqueued with retry counters.
* **Blast Radius**: Isolated entirely to the EHR synchronization workflow; internal AI diagnostic inference and patient record retrieval remained operational.

---

## 4. Root Cause Analysis (5 Whys)

1. **Why did synchronization jobs begin failing?**  
   The external Mock EHR service returned HTTP 500 Internal Server Errors on `/api/v1/patients/sync`.
2. **Why did workers not crash when encountering HTTP 500s?**  
   The worker loop implements resilient exception handling, catching request errors and observing failure metrics rather than terminating the process.
3. **Why did the queue not exhaust memory during the outage?**  
   Workers used capped exponential backoff and a Dead-Letter Queue (DLQ) limit of `max_retries = 3`.
4. **How was the issue detected without human user reports?**  
   Prometheus continuously scrapes the worker metrics exporter (`:9100/metrics`) and evaluated `EHRFailureRateHigh` rule within 10 seconds.
5. **How did the system recover?**  
   Once the upstream service recovered, the background worker pool picked up retrying jobs from Redis and synchronized records into PostgreSQL.

---

## 5. Telemetry & Log Artifacts

### 1. Prometheus Alert State
```yaml
- alert: EHRFailureRateHigh
  expr: rate(ehr_requests_total{status=~"5.."}[1m]) > 0
  state: FIRING
  severity: warning
  summary: "External EHR sync failures detected"
```

### 2. Microservice Logs (Structured JSON)
```json
{"time": "2026-09-18T15:35:01Z", "service": "worker", "worker_id": "prod-worker-1", "level": "ERROR", "message": "Error processing job=job-ehr-901: EHR Service rejected sync with HTTP 500: Internal Server Error"}
{"time": "2026-09-18T15:35:01Z", "service": "worker", "worker_id": "prod-worker-1", "level": "WARNING", "message": "Re-enqueued job=job-ehr-901 for retry #1"}
{"time": "2026-09-18T15:35:23Z", "service": "worker", "worker_id": "prod-worker-1", "level": "INFO", "message": "Successfully finished job=job-ehr-901 in 0.045s"}
```

---

## 6. Preventative Action Items & Architectural Guardrails

| Action Item | Owner | Priority | Target Milestone |
|---|---|:---:|:---:|
| **Implement Circuit Breaker Pattern**: Add PyBreaker around outbound EHR HTTP clients to fast-fail syncs during prolonged 3rd-party outages. | Reliability Eng | High | Phase 7 |
| **Dedicated Dead-Letter Queue (DLQ)**: Route jobs exceeding 3 retries to a dedicated `healthcare:jobs:dlq` topic for manual review. | Backend Team | High | Implemented ✅ |
| **Horizontal Worker Auto-Scaling**: Configure Prometheus alert `QueueBacklogSpike` to trigger automated worker scaling via Docker/Kubernetes HPA. | DevOps Eng | Medium | In Progress |
| **External Partner SLA Dashboard**: Create dedicated Grafana dashboard tracking 3rd-party partner latency percentiles and error quotas. | Observability Eng | Medium | Phase 7 |
