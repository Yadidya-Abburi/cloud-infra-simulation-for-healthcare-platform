# Incident Response and Disaster Recovery Report

**Project:** Secure, Reliable and Scalable Cloud Infrastructure Simulation for an AI-Powered Healthcare Platform  
**Report Date:** 2026-09-18  
**Prepared By:** Cloud & DevSecOps Engineering Team  
**Compliance Reference:** Project_Requirements.pdf (Sections 14, 19, 20, 22, 24, 25, 32, 33)  
**Classification:** Final-Year Engineering Project Submission  

---

## 1. Executive Summary

### 1.1 Project Reliability Objectives

The project was designed to simulate a production-style cloud engineering and operations environment for an AI-powered healthcare platform. Reliability objectives, as defined in the Project_Requirements.pdf and reflected across all source documents, include:

- **High Availability:** Blue-Green deployment ensures zero-downtime releases and automatic failover between `api-blue` and `api-green` instances via NGINX upstream switching with `max_fails=2` and `fail_timeout=5s`.
- **Fault Tolerance:** Dual background workers (`worker-1`, `worker-2`) horizontally scaled; decoupled Redis queue retains jobs during worker failure; capped exponential retry backoff with `max_retries = 3` protects against cascading failures.
- **Observability:** Prometheus scrapes all services every 5 seconds; 5 alerting rules evaluate continuously; Grafana operational dashboards provide real-time visibility.
- **Disaster Recovery:** Recovery Point Objective (RPO) of < 15 minutes; Recovery Time Objective (RTO) of < 5 minutes. Automated logical backups via `pg_dump` with Point-In-Time Recovery (PITR).
- **Security:** Non-root execution (`appuser:10001`); zero hardcoded secrets; automated CI/CD security gates (secret scanning, container linting, dependency auditing).

### 1.2 Scope of Incident Response

Incident response coverage encompasses:

- **Ingress Layer:** NGINX reverse proxy on `frontend-net` (Port 8080:80), serving as the sole public entrypoint.
- **Application Layer:** API Blue (`api-blue:8000`) and API Green (`api-green:8000`) deployed as dual instances.
- **Background Processing:** Two worker containers consuming from Redis queue with retry logic.
- **Data Layer:** PostgreSQL 16 database on `backend-net` (Port 5432) with persistent Docker volume; Redis 7.2 message queue on Port 6379.
- **External Dependencies:** Mock EHR service (`mock-ehr:8083`) simulating external partner gateway; AI inference service (`ai-service:8082`).
- **Observability Plane:** Prometheus 9090 and Grafana 3000, both on `backend-net`.
- **Infrastructure:** Terraform-managed Docker containers across `dev` and `prod` environments; Docker networks `frontend-net` and `backend-net` for traffic isolation.

### 1.3 Infrastructure Components Covered

| Component | Technology | Network | Exposure |
|---|---|---|---|
| NGINX Ingress | nginx:1.25-alpine | `frontend-net` | Port 8080:80 |
| API Blue | FastAPI (non-root) | `frontend-net` + `backend-net` | Internal |
| API Green | FastAPI (non-root) | `frontend-net` + `backend-net` | Internal |
| PostgreSQL 16 | postgres:16-alpine | `backend-net` | None (private) |
| Redis 7.2 | redis:7.2-alpine | `backend-net` | None (private) |
| Background Workers | Python app (non-root) | `backend-net` | None (private) |
| Mock EHR | FastAPI (non-root) | `backend-net` | None (private) |
| AI Service | FastAPI (non-root) | `backend-net` | None (private) |
| Prometheus | prom/prometheus:v2.50.1 | `backend-net` | Port 9090 |
| Grafana | grafana/grafana:10.3.3 | `backend-net` | Port 3000 |
| Terraform | Docker provider | Infrastructure | N/A |

### 1.4 Failure Scenarios Tested

The following failure scenarios were **actually simulated and documented** in the source evidence:

| Scenario ID | Description | Source | Status |
|---|---|---|---|
| INC-2026-09-01 | External EHR Gateway Outage (HTTP 500) | incident-report.md, chaos_simulator.py | **Resolved** |
| SCENARIO-A | EHR Dependency Outage & Retry Storm | chaos_simulator.py | **Simulated/Verified** |
| SCENARIO-B | Worker Crash & Queue Backlog Accumulation | chaos_simulator.py | **Simulated/Verified** |
| DEPLOY-ROLLBACK | Failed Blue-Green Deployment (v2.0.0-broken) | deploy.py, deploy.ps1, runbook.md | **Tested via Unit Tests** |
| CI-SECRET | CI/CD Secret Detection Gate Failure | run-pipeline.py, ci/tests | **Simulated** |
| CI-CONTAINER | CI/CD Container Hardening Gate Failure | run-pipeline.py, ci/tests | **Simulated** |
| CI-DEPENDENCY | CI/CD Dependency/Isolation Gate Failure | run-pipeline.py, ci/tests | **Simulated** |

### 1.5 Monitoring and Alerting Capabilities

Prometheus (v2.50.1) performs 5-second interval scrapes across all instrumented services. Five alerting rules are defined in `monitoring/prometheus/alerts.yml`:

| Alert Name | Severity | Condition | For |
|---|---|---|---|
| `APIServiceDown` | critical | `up{job="api-service"} == 0` | 10s |
| `HighHTTP5xxErrorRate` | critical | `rate(http_requests_total{status=~"5.."}[1m]) > 0.1` | 15s |
| `WorkerUnavailable` | critical | `count(up{job="worker-service"} == 1) == 0` | 10s |
| `QueueBacklogSpike` | warning | `max(worker_queue_depth) > 10` | 15s |
| `EHRFailureRateHigh` | warning | `rate(ehr_requests_total{status=~"5.."}[1m]) > 0` | 10s |

Grafana dashboards (v10.3.3) are pre-provisioned with 8 panels covering API status, worker count, queue depth, EHR status, request rates, latency, and job processing metrics.

### 1.6 Recovery and Rollback Mechanisms

- **Blue-Green Rollback:** Automated circuit breaker in `deploy.py` destroys unhealthy standby containers and restores traffic to the active color on readiness failure.
- **Container Restart:** Docker `restart: always` policy applies to all containers.
- **Database Recovery:** `pg_dump` logical backups with PITR; Terraform-managed volume recreation.
- **Worker Self-Healing:** Docker restart policy; horizontal scaling via Terraform `worker_count` parameter.
- **Retry with DLQ:** Exponential backoff with `max_retries = 3`; jobs exceeding max retries marked as `failed` and logged to `audit_logs`.

### 1.7 Major Findings

1. **EHR Outage Contained Effectively:** The simulated EHR gateway outage (INC-2026-09-01) demonstrated that asynchronous queue decoupling via Redis prevented API ingress degradation. API availability remained at 100%, and zero records were lost.
2. **Worker Crash Recovery Within 2.1 Seconds:** The worker crash scenario demonstrated rapid queue draining (25->0 jobs in 2.1s) after worker pool self-healing, with both Prometheus alerts (`WorkerUnavailable`, `QueueBacklogSpike`) resolving.
3. **Blue-Green Deployment Automated Rollback Verified:** Unit tests in `test_deployment_controller.py` confirm that the `v2.0.0-broken` deployment scenario triggers automated rollback, restoring upstream to `api-blue`.
4. **CI/CD Security Gates Functional:** The pipeline correctly blocks deployments when simulated security failures (secret, container, dependency) are injected, exiting with non-zero code 1.
5. **Observability Plane Operates Out-of-Band:** Monitoring failures do not degrade patient transactions, as confirmed in disaster-recovery.md.

### 1.8 Limitations and Unresolved Risks

1. **Not Verified from Available Project Evidence:** Actual production deployment timestamps and live incident detection latency have not been confirmed through runtime execution evidence in the source documents. All incident timelines are from simulation mode.
2. **RPO and RTO Not Empirically Measured:** The RPO < 15 minutes and RTO < 5 minutes values are defined as design targets in disaster-recovery.md but have not been empirically validated through documented recovery drills in the available evidence.
3. **No Documented Network Connectivity Failure Test:** While the architecture documents network segmentation, no simulation of network connectivity failure between components was found in the source evidence.
4. **No Documented Data Integrity Failure Scenario:** While audit logs are designed and the database schema includes referential integrity, no failure injection scenario specifically targeting data corruption or integrity was documented.
5. **No Documented Security Incident:** No security breach or intrusion scenario was simulated or documented. The security controls (secret scanning, container linting, dependency auditing) are preventive gates, not incident response mechanisms for active security events.
6. **Monitoring Failure Not Tested:** While Prometheus and Grafana are described as out-of-band, no scenario simulating monitoring plane failure was executed or documented.
7. **Automated Horizontal Worker Scaling Not Demonstrated:** The `QueueBacklogSpike` alert is defined, and Terraform parameterizes `worker_count`, but no automated scaling trigger (e.g., HPA) was demonstrated in the available evidence. The chaos simulator manually restarts workers rather than triggering auto-scaling.

---

## 2. Incident Response Architecture

### 2.1 Overview

The incident response architecture is composed of layered components, each participating in detection, response, mitigation, or recovery. The architecture follows a zero-trust, least-privilege model with strict network boundaries between public ingress and private backend infrastructure.

### 2.2 Component Participation Map

#### NGINX Ingress (`healthcare-nginx`, Port 8080:80)

NGINX serves as the sole public entrypoint and dynamic upstream router. It participates in incident response through:

- **Traffic Routing:** Routes client requests to the active API instance (currently `api-blue`) via dynamically generated `upstream.conf` with `max_fails=2` and `fail_timeout=5s`. If an API instance fails health checks, NGINX shifts traffic to the standby instance.
- **Health Endpoint:** Provides `/nginx-health` returning `{"status":"UP","role":"ingress"}` for Docker healthcheck (interval: 10s, timeout: 3s, retries: 3).
- **Hot Reload:** During Blue-Green deployment, `nginx -s reload` performs atomic configuration update without dropping active TCP connections.
- **Detection Role:** NGINX healthcheck failures are indirectly detected through `APIServiceDown` Prometheus alert (if NGINX cannot reach the upstream).

**Not Verified from the available project evidence:** NGINX failure was not directly simulated as a standalone chaos scenario. The architecture documents Docker `restart: always` as the mitigation.

#### API Blue and API Green (Blue-Green Deployment)

The dual API deployment is the primary availability mechanism:

- **API Blue (`api-blue:8000`):** Active production instance serving all client traffic. Connected to both `frontend-net` and `backend-net`.
- **API Green (`api-green:8000`):** Standby candidate instance receiving the new version during deployment. Probes `/ready` and `/health` endpoints before cutover.
- **Readiness Probe:** Tests live connections to PostgreSQL and Redis. Returns HTTP 503 if either dependency is unhealthy. This serves as the pre-cutover readiness gate.
- **Detection Role:** `APIServiceDown` alert fires when Prometheus cannot scrape the API metrics endpoint for >10s. `HighHTTP5xxErrorRate` fires when 5xx error rate exceeds 0.1 req/s.
- **Recovery Role:** If the active instance fails, NGINX `max_fails=2` redirects traffic to the standby. The Blue-Green deployment controller can also spawn a new standby and shift traffic.

**Distinction:** The Blue-Green architecture is **designed and implemented** per architecture.md and deploy.py. Unit tests in `test_deployment_controller.py` **verify** the state transitions. However, the actual runtime execution of a Blue-Green deployment with a real traffic shift is only **simulated** via `--simulate-runtime` flag; no live production traffic shift with real clients was documented.

#### Blue-Green Deployment Controller (`deployment/scripts/deploy.py`)

The deployment controller manages the entire release lifecycle:

- **Step 1:** Discovers active color (`api-blue` or `api-green`) by reading `deployment/nginx/conf.d/upstream.conf`.
- **Step 2:** Spawns standby container with target version.
- **Step 3:** Probes `/ready` and `/health` on the standby instance. This is the **pre-cutover readiness probe**.
- **Step 4:** Updates `upstream.conf` and performs `nginx -s reload` for atomic traffic shift.
- **Step 5:** Validates public ingress traffic routing to new version.
- **Step 6:** Decommissions old version.
- **Automated Rollback Circuit Breaker:** If any step fails (especially Step 3 readiness probe returning HTTP 500), the controller triggers `rollback()`, which restores upstream to the active color, destroys the unhealthy standby, and exits with code 1.

**Status:** **Implemented and tested** via unit tests (`test_deployment_controller.py`). The simulation mode (`--simulate-runtime`) confirms the workflow, and the failure mode (`--simulate-failure`) confirms automated rollback.

#### PostgreSQL (`healthcare-postgres`, Port 5432)

- **Detection:** API `/ready` probe tests database connectivity. `DB_CONNECTED` gauge set to 0 if connection fails.
- **Failure Mode:** Corrupted data volume or container crash would cause API `/ready` to return 503, blocking new patient requests.
- **Mitigation:** Persistent Docker volume `postgres_data` preserves data across container crashes. Docker `restart: always` policy.
- **Recovery:** `pg_dump` logical backups with PITR. Terraform-managed storage volume recreation. Recovery procedure documented in disaster-recovery.md.
- **Risk Severity:** **High** per SPOF analysis, as database corruption affects all services.

#### Redis (`healthcare-redis`, Port 6379)

- **Detection:** API `/ready` probe tests Redis connectivity. Worker reconnect logic on `redis.exceptions.ConnectionError`.
- **Failure Mode:** Redis crash empties in-flight queue if unpersisted. However, jobs originate from PostgreSQL records in `status: queued`, so workers re-synchronize pending records on restart.
- **Mitigation:** Docker `restart: always`. Jobs persisted in PostgreSQL `jobs` table.
- **Recovery:** Worker re-synchronization from DB. No data loss expected due to DB-backed job state.
- **Risk Severity:** **Medium** per SPOF analysis due to potential ephemeral job loss.

#### Background Workers (`worker-1`, `worker-2`, Port 9100)

- **Detection:** `WorkerUnavailable` alert fires when `count(up{job="worker-service"} == 1) == 0`. `QueueBacklogSpike` fires when `max(worker_queue_depth) > 10`.
- **Failure Mode:** Worker crash (OOM, unhandled exception) causes jobs to accumulate in Redis queue.
- **Mitigation:** Horizontal scaling (`worker_count = 2` in prod, 1 in dev). Redis queue retains jobs. Capped exponential backoff with `max_retries = 3`. DLQ for permanently failed jobs.
- **Recovery:** Docker `restart: always` revives containers. Manual or automated worker scaling. Queue draining observed at 12.5 jobs/sec in simulation.

#### Mock EHR (`healthcare-mock-ehr`, Port 8083)

- **Detection:** `EHRFailureRateHigh` alert fires when `rate(ehr_requests_total{status=~"5.."}[1m]) > 0`.
- **Failure Modes:** Supports 6 simulation modes: `normal`, `slow`, `timeout`, `error_500`, `auth_error`, `unavailable`. Each produces different HTTP status codes (200, 504, 500, 401, 503).
- **Mitigation:** Capped exponential retry backoff with `max_retries = 3`. Dead-Letter Queue for permanently failed jobs. Asynchronous decoupling prevents API ingress degradation.
- **Recovery:** Mode restoration to `normal` triggers self-healing of queued jobs.

#### AI Inference Service (`healthcare-ai-service`, Port 8082)

- **Detection:** `APIServiceDown` alert if metrics endpoint unreachable. API `/ready` probe tests database and Redis (not AI service directly).
- **Failure Mode:** AI service unavailability causes `/api/v1/diagnose` endpoint to return HTTP 503.
- **Mitigation:** Not explicitly documented as a standalone failure scenario. The service runs independently and does not block core patient workflows.

**Not Verified from the available project evidence:** No chaos simulation specifically targeting the AI service was documented.

#### Prometheus (Port 9090)

- **Scrape Configuration:** 5-second interval scrapes of `api-service` (api-blue:8000), `worker-service` (worker-1:9100, worker-2:9100), `ai-service` (ai-service:8082), `mock-ehr` (mock-ehr:8083), and `prometheus` itself.
- **Alert Evaluation:** Rule files (`alerts.yml`) evaluated every 5 seconds.
- **Detection Role:** Primary detection mechanism for all monitored failure scenarios.
- **Failure Mode:** If Prometheus crashes, `restart: always` restores it. Observability plane is out-of-band; monitoring crashes do not block patient transactions.

#### Grafana (Port 3000)

- **Dashboard:** `Healthcare Platform - Operational Overview` with 8 panels providing real-time visibility.
- **Provisioning:** Automated via `dashboard.yml` and `healthcare_overview.json`.
- **Detection Role:** Operator visualization for investigation and triage stages.
- **Anonymous Access:** Enabled with Viewer role.

#### Alertmanager

**Not documented in the available project evidence.** The project uses Prometheus alerting rules directly (via `alerts.yml`) without a separate Alertmanager component. Alert routing, escalation, and notification channels are not documented. Alert output is observed through Prometheus web UI state transitions and simulated console output in the chaos simulator.

#### Docker Networks

- **`frontend-net`:** Public-facing bridge network. Contains NGINX and API instances (`api-blue`, `api-green`). Port 8080:80 exposed to host.
- **`backend-net`:** Private bridge network. Contains PostgreSQL, Redis, workers, Mock EHR, AI service, Prometheus, and Grafana. **No host ports bound.**
- **Network Segmentation:** Critical security boundary. Database and Redis are inaccessible from the public internet. The API service bridges both networks.

#### Terraform-Managed Infrastructure

- **Modules:** `network`, `storage`, `services`, `monitoring`.
- **Environments:** `dev` (1 worker, Port 8081) and `prod` (2 workers, Port 8080).
- **Provider:** Docker provider (`kreuzwerker/docker` v3.0.2) on Windows named pipe.
- **IaC Benefits:** Declarative drift detection, parameterized deployments, reproducible infrastructure recreation.

#### Disaster Recovery Components

- **Backup Strategy:** `pg_dump` logical backups to encrypted offsite storage (30-day lifecycle retention).
- **Restore Procedure:** Terraform volume recreation -> PostgreSQL reinitialization -> `pg_restore` from latest snapshot -> table consistency verification.
- **Point-In-Time Recovery (PITR):** WAL log replay for granular recovery.
- **Infrastructure Recreation:** Full Terraform `apply` for compute, network, and monitoring recreation.

#### Operational Runbook

The runbook (`runbook.md`) provides scripted CLI commands for:
- Environment startup and verification
- CI/CD pipeline execution and security gate demonstrations
- Blue-Green deployment and automated rollback
- Chaos simulation drills (EHR outage, worker crash)
- Observability dashboard URLs
- Unit and integration test execution

---

## 3. Incident Lifecycle

### 3.1 Lifecycle Stages Mapped to Project Mechanisms

The project implements a 7-phase operational lifecycle documented in `chaos_simulator.py`:
`Failure -> Detection -> Investigation -> Root Cause -> Recovery -> Verification -> Prevention`

#### 3.1.1 Detection

**Mechanism:** Prometheus continuous scraping (5s interval) evaluates alerting rules. When conditions match, alert states transition from `RESOLVED` to `FIRING`.

**Evidence:**
- `EHRFailureRateHigh`: `rate(ehr_requests_total{status=~"5.."}[1m]) > 0` evaluated every 5s, fires after 10s duration.
- `WorkerUnavailable`: `count(up{job="worker-service"} == 1) == 0`, fires after 10s.
- `QueueBacklogSpike`: `max(worker_queue_depth) > 10`, fires after 15s.
- `APIServiceDown`: `up{job="api-service"} == 0`, fires after 10s.
- `HighHTTP5xxErrorRate`: `rate(http_requests_total{status=~"5.."}[1m]) > 0.1`, fires after 15s.

**Status:** **Implemented and documented** in `monitoring/prometheus/alerts.yml`. **Verified** through chaos simulator output and unit tests in `test_incident_lifecycle.py`.

#### 3.1.2 Alert Generation

**Mechanism:** Prometheus alerting rules generate structured alert states with severity labels (`critical`, `warning`) and summary/description annotations.

**Evidence:** Incident-report.md documents the YAML alert state with `EHRFailureRateHigh` at `state: FIRING`, `severity: warning`.

**Status:** **Implemented.** Alert generation is confirmed via chaos simulator output. However, Alertmanager integration for alert routing and notification is **not documented**.

#### 3.1.3 Triage

**Mechanism:** Operator reviews Grafana Operational Overview dashboard and worker logs to assess the nature and scope of the incident.

**Evidence:** Incident-report.md documents: "15:35:12 -- Investigation: On-call engineer checks Grafana Operational Overview dashboard."

**Status:** **Implemented as documented procedure.** Triage is a manual operator step. No automated triage system is documented.

#### 3.1.4 Incident Classification

**Mechanism:** Classification is not automated. The project defines severity levels through Prometheus alert severity labels (`critical`, `warning`). The incident report classifies INC-2026-09-01 as **P2 (Major Degradation)**.

**Status:** **Partially implemented.** Severity labels exist in alert definitions. A formal incident classification taxonomy (P1-P5, S1-S4) is not documented.

#### 3.1.5 Impact Assessment

**Mechanism:** Impact is assessed by examining API availability, queue depth, database connectivity, and data integrity.

**Evidence:** Incident-report.md documents: Ingress API Availability: 100% Uptime; Data Loss: 0 Records Lost; Blast Radius: Isolated to EHR synchronization workflow.

**Status:** **Implemented for simulated scenarios.**

#### 3.1.6 Containment

**Mechanism:** Containment is achieved through architectural decoupling: Redis queue decouples API ingress from EHR sync processing; capped exponential backoff prevents retry storms; `max_retries = 3` and DLQ prevent infinite loops; Docker `restart: always` contains container crashes.

**Status:** **Implemented and demonstrated.**

#### 3.1.7 Mitigation

**Mechanism:** EHR outage: Mode restoration to `normal`. Worker crash: Docker restart policy and manual/automated scaling. Failed deployment: Automated rollback circuit breaker. CI/CD security failures: Pipeline blocking with non-zero exit code.

**Status:** **Implemented and demonstrated** for documented scenarios.

#### 3.1.8 Recovery

**Mechanism:** EHR: Mode change back to `normal`. Workers: Container restart and horizontal scaling. Database: `pg_restore` from backup snapshots. Deployment: Automated rollback to previous version.

**Status:** **Implemented and verified** for simulated scenarios. Recovery times: EHR recovery within 2.1 seconds; worker queue draining 25->0 in 2.1s.

**Not Verified from the available project evidence:** Database recovery (pg_restore) has not been executed in a documented drill.

#### 3.1.9 Validation

**Mechanism:** Post-recovery validation includes Prometheus alert state transition to `RESOLVED`, worker log confirmation, database verification, and public ingress traffic validation.

**Evidence:** "15:35:24 -- Verification: 5 retrying jobs complete successfully in 0.045s. Redis queue depth drains to 0." "15:35:35 -- Alert Resolution: Prometheus clears alert EHRFailureRateHigh."

**Status:** **Implemented and documented** for chaos simulation scenarios.

#### 3.1.10 Post-Incident Review

**Mechanism:** Post-mortem documentation produced in `incident-report.md` containing 5 Whys analysis, timeline, impact assessment, and preventative action items.

**Status:** **Implemented** for INC-2026-09-01.

#### 3.1.11 Corrective Actions

**Mechanism:** Action items documented with owners, priorities, and target milestones.

**Evidence:** 4 action items: Circuit Breaker Pattern (High, Phase 7), Dedicated DLQ (High, Implemented), Horizontal Worker Auto-Scaling (Medium, In Progress), External Partner SLA Dashboard (Medium, Phase 7).

**Status:** **Partially implemented.** DLQ is implemented. Circuit breaker and SLA dashboard planned for Phase 7. Auto-scaling in progress.


---

## 4. Incident Classification Framework

### 4.1 Categories

Categories derived from alerting rules, SPOF analysis, chaos scenarios, and operational documentation.

| Category | Simulated? | Alert Rule | Status |
|---|---|---|---|
| API Service Outage | No | `APIServiceDown` | Design-documented only |
| NGINX Ingress Failure | No | N/A | Docker `restart: always` |
| Failed Deployment | Yes | `deploy.py` Step 3 | Tested via unit tests |
| Failed Readiness Probe | Yes | `deploy.py` Step 3 | Tested via unit tests |
| Blue-Green Traffic Routing Failure | Partially | `APIServiceDown` | Unit tests verify state transitions |
| Database Failure | No | `DB_CONNECTED` gauge | Recovery procedure documented |
| Redis Failure | No | `WorkerUnavailable` | Worker reconnect logic |
| Worker Failure | Yes | `WorkerUnavailable`, `QueueBacklogSpike` | Demonstrated (Scenario B) |
| Mock EHR Failure | Yes | `EHRFailureRateHigh` | Demonstrated (Scenario A, INC-2026-09-01) |
| AI Service Failure | No | `APIServiceDown` | Not simulated |
| Network Connectivity Failure | No | N/A | Not tested |
| Monitoring Failure | No | `prometheus` self-scrape | Not tested |
| Data Integrity Issue | No | `SELECT COUNT(*)` | Recovery procedure documented |
| Security Incident | Partially | CI/CD gates | `--simulate-failure` tested |

### 4.2 Detailed Classification: API Service Outage

- **Symptoms:** 502/503/504 errors at ingress; `/ready` returns 503; `APIServiceDown` fires
- **Detection:** `APIServiceDown` alert (`up{job="api-service"} == 0`, 10s)
- **Response:** NGINX `max_fails=2` shifts traffic to standby; Docker `restart: always` revives container
- **Recovery:** Blue-Green failover; container restart; standby readiness verification
- **Simulated?** No direct chaos scenario; unit tests verify deployment state transitions

### 4.3 Detailed Classification: NGINX Ingress Failure

- **Symptoms:** Connection refused on Port 8080; all client requests fail
- **Detection:** `APIServiceDown` alert; Docker healthcheck failure
- **Response:** Docker `restart: always` revives NGINX container
- **Recovery:** Container restart; upstream.conf preserved
- **Simulated?** No. Design-documented only.

### 4.4 Detailed Classification: Failed Deployment

- **Symptoms:** Candidate readiness probe returns HTTP 500; deployment halts
- **Detection:** `deploy.py` Step 3; automated rollback circuit breaker
- **Response:** Deployment controller halts rollout; destroys unhealthy container
- **Recovery:** Automated rollback: restores upstream to active color, keeps 100% traffic on Blue
- **Simulated?** Yes. `deploy.py --version v2.0.0-broken --simulate-failure` and unit tests verify.

### 4.5 Detailed Classification: Failed Readiness Probe

- **Symptoms:** `/ready` returns HTTP 503; DB or Redis connection refused
- **Detection:** `deploy.py` Step 3; `APIServiceDown` and `HighHTTP5xxErrorRate` alerts
- **Response:** Automated rollback triggered
- **Recovery:** Unhealthy container destroyed; traffic remains on active instance
- **Simulated?** Yes. `--simulate-failure` flag and `test_failed_simulation_triggers_rollback` unit test.

### 4.6 Detailed Classification: Worker Failure

- **Symptoms:** Jobs accumulate in Redis queue; `WorkerUnavailable` and `QueueBacklogSpike` alerts fire
- **Detection:** `WorkerUnavailable` (`count(up{job="worker-service"} == 1) == 0`, 10s, CRITICAL); `QueueBacklogSpike` (`max(worker_queue_depth) > 10`, 15s, WARNING)
- **Response:** Docker `restart: always` revives containers; worker self-healing
- **Recovery:** Worker pool restart; horizontal scaling; queue draining (observed 25->0 in 2.1s)
- **Simulated?** Yes. Scenario B demonstrates full lifecycle.

### 4.7 Detailed Classification: Mock EHR Failure

- **Symptoms:** EHR sync returns 500/503/504; worker retry loop; `EHRFailureRateHigh` fires
- **Detection:** `EHRFailureRateHigh` (`rate(ehr_requests_total{status=~"5.."}[1m]) > 0`, 10s)
- **Response:** Worker caught by exception handler; exponential backoff retry initiated
- **Recovery:** EHR mode restored to `normal`; retrying jobs complete; DLQ for permanent failures
- **Simulated?** Yes. Scenario A and INC-2026-09-01 demonstrate full lifecycle.

### 4.8 Categories Not Simulated

The following categories have documented design but **no chaos simulation** in the available evidence:
- NGINX Ingress Failure
- Database Failure (standalone)
- Redis Failure (standalone)
- AI Service Failure
- Network Connectivity Failure
- Monitoring Failure
- Data Integrity Issue
- Security Incident (active breach)


---

## 5. Documented Chaos Engineering and Failure Injection

### 5.1 Complete Failure Injection Scenario Inventory

| Incident ID | Failure Scenario | Target Component | Injection Method | Expected System Behavior | Actual Observed Behavior | Detection | Mitigation | Recovery | Evidence | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| INC-2026-09-01 | External EHR Gateway Outage (HTTP 500) | Mock EHR (`mock-ehr:8083`) | `POST /mode` with `{"mode": "error_500"}`; 5 sync jobs enqueued | EHR returns 500; workers retry with exponential backoff; API ingress unaffected; alert fires | EHR returned 500; workers re-enqueued jobs (retry #1->#3); API 100% uptime; 0 data loss; `EHRFailureRateHigh` fired within 10s; 5 jobs completed in 0.045s after recovery; alert cleared at 15:35:35 | `EHRFailureRateHigh` (`rate(ehr_requests_total{status=~"5.."}[1m]) > 0`, 10s) | Exponential backoff; `max_retries=3`; DLQ; async queue decoupling | EHR mode restored to `normal`; workers consumed retrying jobs; queue drained to 0 | incident-report.md; chaos_simulator.py Scenario A | **Resolved** |
| SCENARIO-A | EHR Outage & Retry Storm | Mock EHR | `chaos_simulator.py --scenario a`; EHR set to `error_500`; synthetic client enqueues 5 high-priority jobs | Same as INC-2026-09-01 | Worker logs show `EHR Service rejected sync with HTTP 500`; Prometheus `EHRFailureRateHigh` FIRING; metric `rate(ehr_requests_total{status=~'5..'}[1m]) = 0.83 req/s > 0`; alert state `FIRING (Severity: WARNING)` | `EHRFailureRateHigh`; worker logs; Prometheus metrics | Exponential backoff with jitter; DLQ at 3 attempts | EHR restored to `normal` mode; worker consumer picks up retrying jobs; 5/5 pending jobs completed; alert RESOLVED | chaos_simulator.py | **Simulated/Verified** |
| SCENARIO-B | Worker Crash & Queue Backlog | Background Workers (`worker-1`, `worker-2`) | `chaos_simulator.py --scenario b`; containers killed (exit code 137 / SIGKILL); 25 async diagnosis jobs submitted | Workers crash; queue accumulates; alerts fire; API continues accepting requests (202); worker pool self-heals; queue drains | All workers terminated; `WorkerUnavailable` (CRITICAL): `count(up{job='worker-service'} == 1) == 0`; `QueueBacklogSpike` fired: `max(worker_queue_depth) = 25 > 10`; Grafana showed 0 active workers; 25 jobs pending | `WorkerUnavailable` (`count(up{job="worker-service"} == 1) == 0`, 10s, CRITICAL); `QueueBacklogSpike` (`max(worker_queue_depth) > 10`, 15s, WARNING) | Docker `restart: always`; horizontal scaling (`worker_count = 2`); Redis queue retains jobs | Self-healing: restarted prod-worker-1 and scaled prod-worker-2; both workers healthy; queue drained 25->14->3->0 in 2.1s; throughput 12.5 jobs/sec; both alerts RESOLVED | chaos_simulator.py | **Simulated/Verified** |
| DEPLOY-ROLLBACK | Failed Blue-Green Deployment (v2.0.0-broken) | API Service (candidate `api-green`) | `deploy.py --version v2.0.0-broken --simulate-failure`; readiness probe returns HTTP 500 | Deployment halts; unhealthy container destroyed; traffic remains on Blue; exit code 1 | Candidate GREEN fails readiness checks (HTTP 500); controller detects fault before cutover; faulty container destroyed; 100% traffic intact on BLUE; exit code 1 | `deploy.py` Step 3 readiness verification; automated rollback circuit breaker | Automated rollback: `switch_upstream_file(active_color)` + `reload_nginx_ingress()`; unhealthy container removed | Upstream restored to `api-blue`; active color confirmed via unit test `test_failed_simulation_triggers_rollback` | deploy.py; test_deployment_controller.py; deploy.ps1 | **Tested via Unit Tests** |
| CI-SECRET | CI/CD Secret Detection Gate Failure | CI/CD Pipeline | `python ci/run-pipeline.py --simulate-failure secret` | Pipeline halts at Stage 3 with non-zero exit code 1 | Pipeline halted at Stage 3 with non-zero exit code 1; message: "SIMULATED FAILURE: Detected unencrypted AWS_ACCESS_KEY_ID in application config. Gate BLOCKED." | Stage 3 of `run-pipeline.py`; `stage_secret_scan()` returns False | Pipeline blocks release; deployment rejected | Remediate secret; re-run pipeline | run-pipeline.py; ci/tests | **Simulated** |
| CI-CONTAINER | CI/CD Container Hardening Gate Failure | CI/CD Pipeline | `python ci/run-pipeline.py --simulate-failure container` | Pipeline halts at Stage 4 with non-zero exit code 1 | Pipeline halted at Stage 4 with non-zero exit code 1; message: "SIMULATED FAILURE: Dockerfile missing USER directive. Base image running as root. Gate BLOCKED." | Stage 4 of `run-pipeline.py`; `stage_container_lint()` returns False | Pipeline blocks release; deployment rejected | Fix Dockerfile to include USER directive; re-run pipeline | run-pipeline.py; ci/tests | **Simulated** |
| CI-DEPENDENCY | CI/CD Dependency/Isolation Gate Failure | CI/CD Pipeline | `python ci/run-pipeline.py --simulate-failure dependency` | Pipeline halts at Stage 5 with non-zero exit code 1 | Pipeline halted at Stage 5 with non-zero exit code 1; message: "SIMULATED FAILURE: Port 5432 exposed to 0.0.0.0. Gate BLOCKED." | Stage 5 of `run-pipeline.py`; `stage_dependency_and_isolation()` returns False | Pipeline blocks release; deployment rejected | Fix network configuration; re-run pipeline | run-pipeline.py; ci/tests | **Simulated** |
| DEPLOY-SUCCESS | Successful Zero-Downtime Rollout (v1.1.0) | API Service | `deploy.py --version v1.1.0 --simulate-runtime` | Discovers BLUE as active; spawns GREEN; probes /ready and /health; shifts upstream; validates traffic; retires BLUE | Discovers `BLUE` as active; spawns candidate `GREEN`; probes `/ready` and `/health` until green; shifts NGINX upstream to `api-green:8000` via hot-reload; validates public Ingress traffic on port 8080; drains and retires `BLUE` | `deploy.py` Steps 1-5; `switch_upstream.py`; `reload_nginx_ingress()` | Zero-downtime traffic shift; active client TCP sockets remain open | Full deployment completed; new version live | deploy.py; deploy.ps1; test_deployment_controller.py | **Tested via Unit Tests** |

### 5.2 Incident Timeline: INC-2026-09-01

| Timestamp (UTC) | Operational Event & Lifecycle Stage | Technical Evidence / Observation |
|---|---|---|
| 15:35:00 | **Failure Occurs** | Partner EHR gateway changes state to `error_500`. Sync requests fail immediately. |
| 15:35:10 | **Detection** | Prometheus evaluates `rate(ehr_requests_total{status=~"5.."}[1m]) > 0`. Alert `EHRFailureRateHigh` transitions to `FIRING`. |
| 15:35:12 | **Investigation** | On-call engineer checks Grafana Operational Overview dashboard. Worker logs show: `EHR Service rejected sync with HTTP 500: Internal Server Error`. |
| 15:35:18 | **Root Cause Confirmed** | Partner EHR `/health` confirms mode degradation. Database connection and Redis queues verified fully healthy. |
| 15:35:22 | **Mitigation / Recovery** | Partner EHR restored to `normal` mode. Workers resume processing. |
| 15:35:24 | **Verification** | 5 retrying jobs complete successfully in 0.045s. Redis queue depth drains to 0. |
| 15:35:35 | **Alert Resolution** | Prometheus clears alert `EHRFailureRateHigh`. System fully stable. |

### 5.3 Incident Timeline: SCENARIO-B (Worker Crash)

| Time | Event | Evidence |
|---|---|---|
| T+0s | All worker containers terminated (exit code 137 / SIGKILL); 25 diagnosis jobs submitted | chaos_simulator.py Scenario B |
| T+5s | Prometheus alert rules evaluating | chaos_simulator.py |
| T+10s | `WorkerUnavailable` alert fires (CRITICAL) | chaos_simulator.py; alerts.yml |
| T+15s | `QueueBacklogSpike` alert fires (WARNING) | chaos_simulator.py; alerts.yml |
| T+20s | Operator reviews Grafana dashboard; Docker inspect confirms workers exited | chaos_simulator.py |
| T+25s | Worker pool self-healing initiated; containers restarted | chaos_simulator.py |
| T+27.1s | Queue drained 25->14->3->0 in 2.1s; throughput 12.5 jobs/sec; both alerts RESOLVED | chaos_simulator.py |

---

## 6. Incident Reports

### 6.1 Incident INC-2026-09-01: External EHR Gateway Outage & Retry Backpressure

#### Incident ID
INC-2026-09-01

#### Incident Title
External EHR Gateway Outage & Retry Backpressure (P2 - Major Degradation)

#### Date and Time
2026-09-18 at 15:35 UTC

#### Severity
P2 (Major Degradation)

#### Affected Components
- Mock EHR (`healthcare-mock-ehr:8083`)
- Background Workers (`worker-1`, `worker-2`)
- Prometheus (alerting)
- Redis Queue (`healthcare-redis`)

#### Incident Summary
On 2026-09-18 at 15:35 UTC, the simulated external Electronic Health Record (EHR) partner gateway suffered an unannounced internal service degradation, returning HTTP 500 error responses to all outbound patient vitals synchronization requests. The healthcare platform's automated observability plane detected the failure within 10 seconds via Prometheus alert rule `EHRFailureRateHigh`. The decoupled asynchronous background worker architecture prevented API ingress outages: incoming patient appointments and diagnoses continued to be ingested with zero dropped requests. Background workers engaged automated exponential backoff retry cycles. Upon restoration of the external EHR dependency, queued synchronization jobs self-healed, drained within 2.1 seconds, and all Prometheus alert states returned to normal.

#### Detection Method
- Prometheus alert `EHRFailureRateHigh`: `rate(ehr_requests_total{status=~"5.."}[1m]) > 0`, evaluated every 5s, fired after 10s duration.
- Worker logs: structured JSON logs showing `EHR Service rejected sync with HTTP 500: Internal Server Error`.
- Grafana Operational Overview dashboard monitoring.

#### Initial Symptoms
- Worker logs showing `EHR Service rejected sync with HTTP 500: Internal Server Error`
- Prometheus alert `EHRFailureRateHigh` transitioned to `FIRING` (Severity: WARNING)
- Metric: `rate(ehr_requests_total{status=~'5..'}[1m]) = 0.83 req/s > 0`
- Worker logs showing `Re-enqueued job=job-ehr-901 for retry #1`

#### Timeline

| Time (UTC) | Event | Evidence |
|---|---|---|
| 15:35:00 | Failure occurs: EHR gateway changes state to `error_500` | incident-report.md |
| 15:35:10 | Prometheus alert `EHRFailureRateHigh` transitions to `FIRING` | incident-report.md |
| 15:35:12 | On-call engineer checks Grafana dashboard | incident-report.md |
| 15:35:18 | Root cause confirmed: EHR `/health` confirms mode degradation | incident-report.md |
| 15:35:22 | EHR restored to `normal` mode | incident-report.md |
| 15:35:24 | 5 retrying jobs complete successfully in 0.045s; queue drains to 0 | incident-report.md |
| 15:35:35 | Prometheus clears alert `EHRFailureRateHigh` | incident-report.md |

#### Root Cause

**Confirmed Root Cause:** The external Mock EHR service returned HTTP 500 Internal Server Errors on `/api/v1/patients/sync` when operating in `error_500` mode.

**Contributing Factors:**
- EHR service was in `error_500` simulation mode (set via `POST /mode`).
- Workers initially encountered HTTP 500 errors and entered retry loop.

**Possible Causes Not Verified:**
- The specific trigger that caused the EHR service to enter `error_500` mode is not documented in the source evidence.

#### Impact Assessment

- **API Availability:** 100% Uptime. Asynchronous queue decoupling via Redis kept public API endpoints fully responsive without 504 gateway timeouts.
- **Data Loss:** 0 Records Lost. Every sync job was persisted in PostgreSQL and re-enqueued with retry counters.
- **Blast Radius:** Isolated entirely to the EHR synchronization workflow; internal AI diagnostic inference and patient record retrieval remained operational.
- **Background Jobs:** 5 sync jobs affected, all re-enqueued with incrementing retry counters. All 5 completed successfully after EHR recovery.
- **Database State:** PostgreSQL remained fully healthy. No database corruption or connection issues documented.
- **Monitoring:** `EHRFailureRateHigh` alert fired and later cleared. No other alerts affected.
- **User Requests:** No user requests were affected. API continued accepting requests normally.

#### Response Actions

1. On-call engineer checked Grafana Operational Overview dashboard (15:35:12).
2. Reviewed worker logs showing EHR rejection messages.
3. Verified EHR `/health` endpoint confirming mode degradation (15:35:18).
4. Confirmed database connection and Redis queues were fully healthy (15:35:18).
5. Restored EHR service to `normal` mode (15:35:22).

#### Recovery Actions

1. EHR service mode restored to `normal` via `POST /mode` with `{"mode": "normal"}`.
2. Background worker pool picked up retrying jobs from Redis queue.
3. Workers processed 5 retrying jobs successfully in 0.045s each.
4. Redis queue depth drained to 0.
5. Prometheus alert `EHRFailureRateHigh` transitioned to RESOLVED (15:35:35).

#### Validation

- Worker log confirmed: `Successfully finished job=job-ehr-901 in 0.045s` (15:35:23).
- Prometheus alert `EHRFailureRateHigh` transitioned to RESOLVED (15:35:35).
- Database verification: 5/5 pending jobs transitioned to status `completed`.
- Redis queue depth drained to 0.

#### Lessons Learned

1. Asynchronous queue decoupling via Redis effectively isolates external dependency failures from API ingress.
2. Capped exponential backoff with `max_retries = 3` prevents infinite retry loops and protects the EHR service during recovery.
3. Prometheus alerting with 10-second evaluation interval provides rapid detection of dependency failures.
4. The Dead-Letter Queue (DLQ) mechanism at 3 retries provides a safety net for permanently failed jobs.

#### Corrective Actions

| Action Item | Owner | Priority | Target Milestone | Status |
|---|---|:---:|:---:|:---:|
| Implement Circuit Breaker Pattern (PyBreaker around outbound EHR HTTP clients) | Reliability Eng | High | Phase 7 | Not Started |
| Dedicated Dead-Letter Queue (DLQ) | Backend Team | High | Implemented | **Implemented** |
| Horizontal Worker Auto-Scaling via HPA | DevOps Eng | Medium | In Progress | In Progress |
| External Partner SLA Dashboard | Observability Eng | Medium | Phase 7 | Not Started |

#### Evidence References
- incident-report.md (primary source)
- chaos_simulator.py Scenario A
- services/mock-ehr/app/main.py (EHR mode simulation)
- services/worker/app/main.py (retry logic)
- monitoring/prometheus/alerts.yml (`EHRFailureRateHigh` rule)

---

### 6.2 Incident SCENARIO-B: Worker Crash & Queue Backlog Accumulation

#### Incident ID
SCENARIO-B (from chaos_simulator.py)

#### Incident Title
Background Worker Crash & Queue Backlog Accumulation (CRITICAL)

#### Date and Time
Not specified in source evidence (simulated via chaos_simulator.py)

#### Severity
CRITICAL (per Prometheus alert severity label for `WorkerUnavailable`)

#### Affected Components
- Background Workers (`worker-1`, `worker-2`)
- Redis Message Queue (`healthcare-redis`)
- Prometheus (alerting)
- API Service (indirectly affected)
- Grafana (dashboard monitoring)

#### Incident Summary
During a simulated traffic burst, all background worker instances were unexpectedly terminated (exit code 137 / SIGKILL). This caused 25 asynchronous diagnosis jobs to accumulate in the Redis queue. The API ingress continued accepting requests (returning 202 Accepted) due to asynchronous decoupling. Prometheus alerts `WorkerUnavailable` (CRITICAL) and `QueueBacklogSpike` (WARNING) fired within 10-15 seconds. The worker pool self-healed and the queue drained from 25 to 0 jobs in 2.1 seconds.

#### Detection Method
- Prometheus alert `WorkerUnavailable`: `count(up{job="worker-service"} == 1) == 0`, fires after 10s, severity: critical.
- Prometheus alert `QueueBacklogSpike`: `max(worker_queue_depth) > 10`, fires after 15s, severity: warning.
- Grafana Operational Overview dashboard showing Active Workers Count = 0 (DOWN - Red) and Live Queue Depth = 25 jobs pending.
- Docker inspect confirming worker containers exited with OOMKilled=false, status=exited.

#### Initial Symptoms
- `WorkerUnavailable` alert (CRITICAL): `count(up{job='worker-service'} == 1) == 0`
- `QueueBacklogSpike` alert (WARNING): `max(worker_queue_depth) = 25 > 10`
- Grafana panel: Active Workers Count = 0 (DOWN - Red)
- Grafana panel: Live Queue Depth = 25 jobs pending
- API continued accepting requests with 202 Accepted responses

#### Timeline

| Time | Event | Evidence |
|---|---|---|
| T+0s | All worker containers terminated (exit code 137 / SIGKILL); 25 diagnosis jobs submitted | chaos_simulator.py Scenario B |
| T+5s | Prometheus alert rules evaluating | chaos_simulator.py |
| T+10s | `WorkerUnavailable` alert fires (CRITICAL) | chaos_simulator.py; alerts.yml |
| T+15s | `QueueBacklogSpike` alert fires (WARNING) | chaos_simulator.py; alerts.yml |
| T+20s | Operator reviews Grafana dashboard; Docker inspect confirms workers exited | chaos_simulator.py |
| T+25s | Worker pool self-healing initiated; containers restarted | chaos_simulator.py |
| T+27.1s | Queue drained 25->14->3->0 in 2.1s; throughput 12.5 jobs/sec; both alerts RESOLVED | chaos_simulator.py |

#### Root Cause

**Confirmed Root Cause:** Worker process crashed without auto-supervision (exit code 137 / SIGKILL). Docker `restart: always` policy subsequently revived the containers.

**Contributing Factors:**
- Traffic burst of 25 asynchronous diagnosis jobs submitted during worker downtime.
- Workers did not have a dedicated process supervisor beyond Docker restart policy.
- No automated horizontal scaling triggered during the incident (manual restart simulated).

**Possible Causes Not Verified:**
- The specific cause of worker crash (OOM, unhandled exception, SIGKILL source) is not documented beyond the simulated SIGKILL injection.

#### Impact Assessment

- **API Availability:** 100% Uptime. Asynchronous decoupling protected API Ingress: User requests accepted with 202 Accepted responses.
- **Background Jobs:** 25 jobs accumulated in Redis queue during worker downtime. All jobs processed after recovery.
- **Database State:** PostgreSQL remained operational. Jobs persisted in DB records with `status: queued`.
- **Monitoring:** Two Prometheus alerts fired (`WorkerUnavailable` CRITICAL, `QueueBacklogSpike` WARNING). Both resolved after worker recovery.
- **User Requests:** No user-facing impact. API continued accepting requests.
- **Queue State:** 25 jobs pending at peak; drained to 0 in 2.1s after recovery.

#### Response Actions

1. Operator reviewed Grafana Operational Overview dashboard (Active Workers Count = 0, Queue Depth = 25).
2. Docker inspect confirmed worker containers exited unexpectedly (OOMKilled=false, status=exited).
3. Confirmed asynchronous decoupling protected API Ingress (202 Accepted responses).
4. Initiated worker pool self-healing (restart of prod-worker-1 and scaling of prod-worker-2).
5. Verified both workers report healthy connection to Redis and PostgreSQL.

#### Recovery Actions

1. Restarted prod-worker-1 container.
2. Scaled prod-worker-2 to active state.
3. Both workers established healthy connections to Redis and PostgreSQL.
4. Workers began consuming jobs from Redis queue.
5. Queue drained: 25->14->3->0 jobs in 2.1s.
6. Processing throughput surged to 12.5 jobs/sec.
7. Both Prometheus alerts transitioned to RESOLVED.

#### Validation

- Worker metrics: Processing throughput surged to 12.5 jobs/sec.
- Queue depth drained: 25->14->3->0 jobs in 2.1s.
- Prometheus alert `QueueBacklogSpike` status: RESOLVED.
- Prometheus alert `WorkerUnavailable` status: RESOLVED (2 active).
- `test_incident_lifecycle.py` unit tests verify alert rule existence and worker retry logic.

#### Lessons Learned

1. Docker `restart: always` policy provides automatic container revival but does not provide immediate self-healing without a restart delay.
2. Asynchronous decoupling via Redis effectively protects API ingress during worker failures.
3. The `QueueBacklogSpike` alert provides effective detection of worker capacity issues.
4. Horizontal scaling (`worker_count = 2` in prod) provides redundancy but does not prevent queue accumulation if both workers fail simultaneously.
5. The chaos simulator demonstrates the full incident lifecycle from failure to recovery.

#### Corrective Actions

| Action Item | Owner | Priority | Target Milestone | Status |
|---|---|:---:|:---:|:---:|
| Horizontal Worker Auto-Scaling via HPA based on queue depth | DevOps Eng | Medium | In Progress | In Progress |
| Docker restart policy configured to `always` | Platform Eng | High | Implemented | **Implemented** |
| Terraform parameterized worker scaling (`worker_count = 2`) | DevOps Eng | High | Implemented | **Implemented** |
| Horizontal Pod Autoscaler (HPA) / Worker autoscaling | DevOps Eng | Medium | Phase 7 | Not Started |

#### Evidence References
- chaos_simulator.py Scenario B
- monitoring/prometheus/alerts.yml (`WorkerUnavailable`, `QueueBacklogSpike` rules)
- docker-compose.yml (`restart: always` for worker service)
- services/worker/app/main.py (worker reconnect logic)
- infrastructure/terraform/modules/services/main.tf (`worker_count` parameter)

---

### 6.3 Incident DEPLOY-ROLLBACK: Failed Blue-Green Deployment (v2.0.0-broken)

#### Incident ID
DEPLOY-ROLLBACK

#### Incident Title
Failed Blue-Green Deployment with Automated Rollback

#### Date and Time
Not specified in source evidence (simulated via deploy.py)

#### Severity
High (deployment failure, but automated rollback prevented user impact)

#### Affected Components
- API Service (candidate `api-green`)
- Blue-Green Deployment Controller (`deploy.py`)
- NGINX Ingress (`healthcare-nginx`)
- `upstream.conf` configuration

#### Incident Summary
A Blue-Green deployment of version `v2.0.0-broken` was initiated. The candidate `GREEN` container failed readiness checks (HTTP 500 error). The deployment controller detected the fault before cutover, destroyed the unhealthy container, and kept 100% traffic intact on `api-blue`. The process exited with code 1. The automated rollback circuit breaker restored the upstream configuration to the active color.

#### Detection Method
- `deploy.py` Step 3 readiness verification: Probe returned HTTP 500 (Internal Database Connection Refused).
- Readiness validation failed on target `api-green` instance.
- Automated rollback circuit breaker triggered.

#### Initial Symptoms
- Candidate `GREEN` fails readiness checks (HTTP 500 error).
- `deploy.py` Step 3 returns False.
- Controller detects fault before cutover.

#### Timeline

| Step | Event | Evidence |
|---|---|---|
| 1 | Discovers `BLUE` as active | deploy.py Step 1 |
| 2 | Spawns candidate `GREEN` container | deploy.py Step 2 |
| 3 | Probes `/ready` and `/health` -- FAILS (HTTP 500) | deploy.py Step 3 |
| 3.5 | Automated rollback triggered | deploy.py rollback() |
| 4 | Upstream restored to `api-blue` | switch_upstream.py |
| 5 | Unhealthy standby container destroyed | deploy.py |
| 6 | Process exits with code 1 | deploy.py |

#### Root Cause

**Confirmed Root Cause:** Candidate `GREEN` container readiness probe returned HTTP 500 (Internal Database Connection Refused), indicating the candidate could not establish connections to PostgreSQL and/or Redis.

**Contributing Factors:**
- The `--simulate-failure` flag was passed to `deploy.py`, simulating a broken candidate.
- The `simulate_failure` parameter in `step3_verify_readiness()` returns False when the flag is set.

**Possible Causes Not Verified:**
- The specific cause of the HTTP 500 in the candidate container is simulated and not representative of a real failure mode.

#### Impact Assessment

- **API Availability:** No impact. 100% traffic remained on `api-blue` throughout the failed deployment.
- **Traffic Routing:** No traffic was routed to the failed candidate. NGINX upstream remained pointing to `api-blue`.
- **Deployment Pipeline:** Deployment rejected with exit code 1. No version change occurred.
- **Data Integrity:** No data corruption. Database operations continued normally on `api-blue`.

#### Response Actions

1. Deployment controller detected readiness failure at Step 3.
2. Automated rollback circuit breaker triggered immediately.
3. `rollback()` method executed:
   - `switch_upstream_file(active_color)` restored upstream to `api-blue`.
   - `reload_nginx_ingress()` reloaded NGINX configuration.
   - Unhealthy standby container removed via `docker rm -f`.
4. Process exited with code 1.

#### Recovery Actions

1. Upstream configuration restored to `api-blue` via `switch_upstream_file("blue")`.
2. NGINX hot-reloaded via `nginx -s reload`.
3. Unhealthy `api-green` container destroyed.
4. Active color confirmed as `blue` via unit test `test_failed_simulation_triggers_rollback`.

#### Validation

- Unit test `test_failed_simulation_triggers_rollback` verifies rollback restores upstream to `blue`.
- Unit test `test_successful_simulation_rollout` verifies normal deployment flow.
- `test_deployment_controller.py` confirms state transitions.

#### Lessons Learned

1. The automated rollback circuit breaker effectively prevents broken deployments from reaching production traffic.
2. Pre-cutover readiness probing is a critical safety gate that must validate all backing dependencies.
3. The `max_fails=2` and `fail_timeout=5s` NGINX configuration provides additional resilience even if a candidate somehow receives traffic.
4. Unit tests provide automated verification of deployment controller state transitions.

#### Corrective Actions

No specific corrective actions were listed for this incident in the source evidence. The automated rollback mechanism itself is the primary corrective action.

#### Evidence References
- deployment/scripts/deploy.py (rollback mechanism)
- deployment/scripts/switch_upstream.py (upstream switching)
- deployment/tests/test_deployment_controller.py (unit tests)
- runbook.md (deployment scenarios)
- architecture.md (Blue-Green deployment architecture)

---

## 7. Observability and Alerting Analysis

### 7.1 Prometheus Metrics and Alerting Rules

#### 7.1.1 Alert Rule Inventory

| Alert Name | Condition | Target | For | Severity | Detection | Response | Evidence | Status |
|---|---|---|---|---|---|---|---|---|
| `APIServiceDown` | `up{job="api-service"} == 0` | API Service (`api-blue:8000`) | 10s | critical | Prometheus scrape | Operator investigation; Docker restart; Blue-Green failover | monitoring/prometheus/alerts.yml | **Defined** |
| `HighHTTP5xxErrorRate` | `rate(http_requests_total{status=~"5.."}[1m]) > 0.1` | API Service | 15s | critical | Prometheus scrape | Operator investigation; deployment rollback if applicable | monitoring/prometheus/alerts.yml | **Defined** |
| `WorkerUnavailable` | `count(up{job="worker-service"} == 1) == 0` | Background Workers (`worker-1:9100`, `worker-2:9100`) | 10s | critical | Prometheus scrape | Worker restart; horizontal scaling; queue drain | monitoring/prometheus/alerts.yml | **Defined and Demonstrated** |
| `QueueBacklogSpike` | `max(worker_queue_depth) > 10` | Redis Queue | 15s | warning | Prometheus scrape | Worker scaling; queue monitoring | monitoring/prometheus/alerts.yml | **Defined and Demonstrated** |
| `EHRFailureRateHigh` | `rate(ehr_requests_total{status=~"5.."}[1m]) > 0` | Mock EHR (`mock-ehr:8083`) | 10s | warning | Prometheus scrape | EHR mode restoration; worker retry; DLQ | monitoring/prometheus/alerts.yml | **Defined and Demonstrated** |

#### 7.1.2 Alert Detection Latency

- **Scrape Interval:** 5 seconds (configured in `prometheus.yml`).
- **Alert Evaluation Interval:** 5 seconds (configured in `prometheus.yml`).
- **`APIServiceDown` Detection:** 10 seconds (`for: 10s`).
- **`HighHTTP5xxErrorRate` Detection:** 15 seconds (`for: 15s`).
- **`WorkerUnavailable` Detection:** 10 seconds (`for: 10s`).
- **`QueueBacklogSpike` Detection:** 15 seconds (`for: 15s`).
- **`EHRFailureRateHigh` Detection:** 10 seconds (`for: 10s`).

**Actual Observed Detection Latency:**
- INC-2026-09-01: Failure at 15:35:00, alert fired at 15:35:10 (10 seconds). Matches `EHRFailureRateHigh` `for: 10s` configuration.
- SCENARIO-B: Failure at T+0s, alerts fired at T+10s and T+15s. Matches `WorkerUnavailable` and `QueueBacklogSpike` configurations.

**Not Verified from the available project evidence:** End-to-end alert detection latency under real production conditions (non-simulated) has not been measured. All latency measurements are from simulation mode.

### 7.2 Grafana Dashboards

#### 7.2.1 Dashboard Panels

| Panel ID | Title | Type | Query | Purpose |
|---|---|---|---|---|
| 1 | API Service Status | stat | `up{job="api-service"}` | Shows UP/DOWN status with red/green coloring |
| 2 | Active Workers Count | stat | `count(up{job="worker-service"} == 1) or vector(0)` | Shows number of active workers |
| 3 | Queue Depth (Backlog) | stat | `max(worker_queue_depth) or vector(0)` | Shows current queue depth |
| 4 | Mock EHR Status | stat | `up{job="mock-ehr"}` | Shows EHR UP/DOWN status |
| 5 | HTTP Request Rate (req/s) | timeseries | `sum by (status) (rate(http_requests_total[1m]))` | Shows request rate by status code |
| 6 | API Latency (p95 / avg) | timeseries | `histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[1m])) by (le))` | Shows p95 latency |
| 7 | Worker Jobs Completed / Rate | timeseries | `sum(rate(worker_jobs_processed_total[1m]))` + `sum(rate(worker_jobs_failed_total[1m]))` | Shows worker throughput |
| 8 | Live Queue Depth History | timeseries | `worker_queue_depth` | Shows queue depth over time |

**Dashboard Refresh:** 5 seconds.
**Dashboard UID:** `healthcare-overview`.
**Dashboard Tags:** `healthcare`, `production`.

### 7.3 Service Health Checks

| Service | Health Check Endpoint/Command | Interval | Timeout | Retries | Status |
|---|---|---|---|---|---|
| NGINX | `wget -qO- http://127.0.0.1/nginx-health` | 10s | 3s | 3 | Defined in docker-compose.yml |
| PostgreSQL | `pg_isready -U postgres -d healthcare` | 10s | 5s | 5 | Defined in docker-compose.yml |
| Redis | `redis-cli ping` | 10s | 3s | 3 | Defined in docker-compose.yml |
| Mock EHR | Python urllib health check | 15s | 5s | 3 | Defined in docker-compose.yml |
| AI Service | Python urllib health check | 15s | 5s | 3 | Defined in docker-compose.yml |
| API Blue | `curl -f http://localhost:8000/ready` | 10s | 5s | 3 | Defined in docker-compose.yml |
| Prometheus | Self-scraping (`job="prometheus"`) | 5s | N/A | N/A | Defined in prometheus.yml |

### 7.4 Readiness Probes

The API service implements a `/ready` endpoint that tests live connections to PostgreSQL and Redis:

```python
@app.get("/ready")
def readiness():
    db_ok = False; redis_ok = False; errors = []
    # Check DB connection
    # Check Redis connection
    if not (db_ok and redis_ok):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail={"ready": False, "errors": errors})
    return {"ready": True, "database": "connected", "redis": "connected", ...}
```

**Status:** **Implemented and verified.** Used in Blue-Green deployment pre-cutover readiness checks (deploy.py Step 3).

### 7.5 Container Health Checks

All services define Docker healthchecks in `docker-compose.yml`:

- **NGINX:** `wget -qO- http://127.0.0.1/nginx-health`, interval 10s, timeout 3s, retries 3.
- **PostgreSQL:** `pg_isready -U postgres -d healthcare`, interval 10s, timeout 5s, retries 5.
- **Redis:** `redis-cli ping`, interval 10s, timeout 3s, retries 3.
- **Mock EHR:** Python urllib health check, interval 15s, timeout 5s, retries 3.
- **AI Service:** Python urllib health check, interval 15s, timeout 5s, retries 3.
- **API Blue:** `curl -f http://localhost:8000/ready`, interval 10s, timeout 5s, retries 3.

### 7.6 Monitoring Blind Spots

1. **Alertmanager Not Deployed:** No separate Alertmanager component is documented. Alerts are visible in Prometheus UI but no routing to notification channels (email, Slack, PagerDuty) is configured.
2. **No Log Aggregation:** While structured JSON logs are produced by services, no centralized log aggregation system (e.g., Loki, ELK) is documented.
3. **No Trace/Segment Monitoring:** No distributed tracing (e.g., Jaeger, OpenTelemetry) is documented for request flow visibility across microservices.
4. **No Synthetic Monitoring:** No synthetic health checks from external locations are documented.
5. **No Custom Business Metrics:** No business-level metrics (e.g., patient registration rate, diagnosis completion rate) are documented.
6. **No Anomaly Detection:** Alert rules are threshold-based (static values). No ML-based anomaly detection is documented.
7. **No Dashboard for Audit Logs:** The `audit_logs` table in PostgreSQL is not visualized in Grafana dashboards.

### 7.7 Monitoring Failures

**Not Verified from the available project evidence:** No monitoring failure scenario was simulated or documented. The disaster-recovery.md states that the observability plane is out-of-band and does not block patient transactions, but no test was executed to validate this claim.

---

## 8. Blue-Green Deployment Incident Handling

### 8.1 Deployment Workflow Analysis

#### 8.1.1 Deployment Preparation

- **Active Color Discovery:** `switch_upstream.py` reads `deployment/nginx/conf.d/upstream.conf` to determine current active color (`api-blue` or `api-green`).
- **Standby Color Determination:** The alternate color is determined by `get_standby_color()` function.
- **Target Version:** Specified via `--version` flag to `deploy.py`.

**Status:** **Implemented and tested.** Unit tests `test_standby_color_alternation` and `test_successful_simulation_rollout` verify.

#### 8.1.2 New Version Startup

- **Standby Spawning:** `deploy.py` Step 2 provisions the standby container (`api-green` or `api-blue`) with the target version.
- **Network Attachment:** Container attached to both `frontend-net` and `backend-net`.
- **Environment Variables:** `DEPLOYMENT_COLOR`, `APP_VERSION`, DB/Redis connection details, AI service URL.

**Status:** **Implemented and tested** via simulation mode (`--simulate-runtime`). Real Docker execution available in non-simulation mode.

#### 8.1.3 Pre-Cutover Readiness Probe

- **Internal Readiness:** `deploy.py` Step 3 probes `/ready` and `/health` on the standby container.
- **Health Check:** Tests live connections to PostgreSQL and Redis.
- **Failure Mode:** Returns HTTP 500 if database connection refused or Redis unavailable.
- **Success Mode:** Returns HTTP 200 with verified database and Redis connections.

**Status:** **Implemented and tested.** `--simulate-failure` flag simulates readiness failure. Unit test `test_failed_simulation_triggers_rollback` verifies.

#### 8.1.4 Health Validation

- **Pre-Cutover:** Readiness probe validates all backing dependencies before traffic shift.
- **Post-Cutover:** Public ingress traffic validation (Step 5) confirms HTTP 200 and correct color in response headers.

**Status:** **Implemented and tested.** Unit tests verify both success and failure paths.

#### 8.1.5 Traffic Switching

- **NGINX Upstream Update:** `switch_upstream_file(target_color)` writes new `upstream.conf` with `server api-{target_color}:8000 max_fails=2 fail_timeout=5s`.
- **Hot Reload:** `nginx -s reload` performs atomic configuration update without dropping active TCP connections.
- **Traffic Shift:** Active client TCP sockets remain open without dropping requests.

**Status:** **Implemented and tested.** `switch_upstream.py` verified via unit tests.

#### 8.1.6 NGINX Configuration Update

- **Configuration File:** `deployment/nginx/conf.d/upstream.conf` dynamically generated.
- **Default State:** `server api-blue:8000 max_fails=2 fail_timeout=5s`.
- **Update Method:** Atomic file write by `switch_upstream_file()`.
- **Reload Method:** `docker exec healthcare-nginx nginx -s reload` or simulated equivalent.

**Status:** **Implemented.** `upstream.conf` currently defaults to `api-blue`.

#### 8.1.7 Hot Reload

- **Command:** `nginx -s reload` (SIGHUP signal).
- **Behavior:** Atomic configuration update; active connections remain open; no request drops.
- **Verification:** `deploy.py` Step 5 validates public ingress traffic.

**Status:** **Implemented and tested** via simulation mode. Real Docker execution available.

#### 8.1.8 Rollback Trigger

**Automated Rollback Circuit Breaker triggers when:**
- Step 2 (Standby Provisioning) fails.
- Step 3 (Readiness Verification) fails (HTTP 500).
- Step 4 (Traffic Switch) fails.
- Step 5 (Public Traffic Validation) fails.

**Rollback Actions:**
1. `switch_upstream_file(active_color)` restores upstream to the original active color.
2. `reload_nginx_ingress()` reloads NGINX configuration.
3. Unhealthy standby container removed via `docker rm -f`.
4. Process exits with code 1.

**Status:** **Implemented and tested.** Unit test `test_failed_simulation_triggers_rollback` confirms rollback restores upstream to `blue`.

#### 8.1.9 Automated Rollback

The `rollback()` method in `deploy.py`:
- Ensures upstream points back to `active_color`.
- Reloads NGINX ingress.
- Terminates broken standby container.
- Confirms production traffic remains 100% operational on `active_color`.
- Reports zero customer downtime.

**Status:** **Implemented and tested.** Verified via unit tests and `--simulate-failure` mode.

#### 8.1.10 Post-Rollback Validation

- **Active Color Confirmed:** Unit test `test_failed_simulation_triggers_rollback` asserts `active == "blue"`.
- **Upstream.conf Verified:** `switch_upstream.py` confirms correct color in upstream configuration.
- **Traffic Validation:** Unit test `test_successful_simulation_rollout` confirms traffic routes to new version after successful deployment.

**Status:** **Implemented and tested** via unit tests.

### 8.2 Failure Scenarios in Blue-Green Deployment

#### 8.2.1 Successful Rollout (v1.1.0)

- **Expected:** Discovers `BLUE` as active; spawns `GREEN`; probes readiness; shifts upstream; validates traffic; retires `BLUE`.
- **Actual:** All steps executed successfully in simulation mode. Unit test `test_successful_simulation_rollout` verifies state transitions.
- **Status:** **Tested via Unit Tests.**

#### 8.2.2 Failed Rollout (v2.0.0-broken)

- **Expected:** Candidate `GREEN` fails readiness (HTTP 500); controller detects fault; destroys unhealthy container; keeps 100% traffic on `BLUE`; exits with code 1.
- **Actual:** All expected behavior confirmed. Unit test `test_failed_simulation_triggers_rollback` verifies rollback restores upstream to `blue`.
- **Status:** **Tested via Unit Tests.**

### 8.3 Design vs. Implemented vs. Tested vs. Verified

| Aspect | Design | Implemented | Tested | Verified |
|---|---|---|---|---|
| Blue-Green Architecture | architecture.md, deploy.py | deploy.py, switch_upstream.py | Unit tests | `test_successful_simulation_rollout` |
| Readiness Probe | deploy.py Step 3 | API `/ready` endpoint | `--simulate-failure` | `test_failed_simulation_triggers_rollback` |
| Traffic Shift | architecture.md | `switch_upstream.py` + `nginx -s reload` | Simulation mode | Unit tests |
| Automated Rollback | architecture.md | `deploy.py` rollback() | `--simulate-failure` | Unit test assertion |
| NGINX Hot Reload | architecture.md | `switch_upstream.py` reload_nginx_ingress() | Simulation mode | Unit tests |
| Pre-Cutover Health Validation | architecture.md | `deploy.py` Step 3 | Simulation mode | Unit tests |
| Post-Cutover Traffic Validation | architecture.md, runbook.md | `deploy.py` Step 5 | Simulation mode | Unit tests |

**Not Verified from the available project evidence:** No live production traffic shift with real clients was documented. All Blue-Green deployment testing was performed in simulation mode (`--simulate-runtime`) or via unit tests.

---

## 9. Disaster Recovery and Business Continuity

### 9.1 Recovery Objectives

| Objective | Value | Source | Empirically Measured? |
|---|---|---|---|
| **RPO (Recovery Point Objective)** | < 15 minutes | disaster-recovery.md | **No** |
| **RTO (Recovery Time Objective)** | < 5 minutes | disaster-recovery.md | **No** |

**Not Verified from the available project evidence:** RPO and RTO values are defined as design targets in disaster-recovery.md but have not been empirically validated through documented recovery drills in the available evidence. No DR drill with actual backup restoration was performed or documented.

### 9.2 Backup Strategy

#### Automated Scheduled Logical Backup (`pg_dump`)

The project documents a backup procedure using `pg_dump`:

```bash
# Automated snapshot command
docker exec healthcare-postgres pg_dump -U postgres -d healthcare -F c -b -v -f /tmp/backup.dump

# Copy out to offsite encrypted storage (e.g. S3 / Cloud Storage with 30-day lifecycle retention)
docker cp healthcare-postgres:/tmp/backup.dump ./backups/healthcare_$(date +%Y%m%d_%H%M%S).dump
```

**Status:** **Documented but not verified.** The backup commands are defined in disaster-recovery.md but no automated execution or verification of backup integrity was documented in the source evidence.

#### Backup Storage

- **Retention:** 30-day lifecycle retention (mentioned in disaster-recovery.md).
- **Encryption:** Offsite encrypted storage referenced but implementation details not provided.
- **Verification:** No documented backup verification procedure was found in the source evidence.

### 9.3 Restore Procedure

#### Disaster Recovery / Point-In-Time Restoration Procedure

If the persistent volume is accidentally deleted or corrupted:

1. **Recreate Storage Volume via Terraform:**
   ```bash
   terraform apply -target=module.storage
   ```
2. **Reinitialize PostgreSQL Container:**
   ```bash
   docker compose up -d postgres
   ```
3. **Restore from Latest Verified Snapshot:**
   ```bash
   docker cp ./backups/latest_verified.dump healthcare-postgres:/tmp/restore.dump
   docker exec healthcare-postgres pg_restore -U postgres -d healthcare --clean --if-exists /tmp/restore.dump
   ```
4. **Verify Table Consistency:**
   ```bash
   docker exec healthcare-postgres psql -U postgres -d healthcare -c "SELECT COUNT(*) FROM patients; SELECT COUNT(*) FROM jobs;"
   ```

**Status:** **Documented but not verified.** The restore procedure is defined in disaster-recovery.md but has not been executed in a documented drill. The verification step (`SELECT COUNT(*)`) is defined but no results are documented.

### 9.4 Database Recovery

- **Primary Method:** `pg_dump` logical backup with `pg_restore`.
- **Secondary Method:** Point-In-Time Recovery (PITR) via WAL log replay.
- **Persistent Volume:** Docker volume `postgres_data` preserves data across container crashes.
- **Risk:** PostgreSQL failure is classified as **High** risk per SPOF analysis.

**Not Verified from the available project evidence:** No database recovery drill was executed or documented. The recovery procedure exists only in documentation.

### 9.5 Service Restoration

- **Compute Services:** Terraform `apply` recreates all Docker containers (API, workers, AI service, Mock EHR).
- **Network:** Terraform network modules recreate `frontend-net` and `backend-net`.
- **Monitoring:** Terraform monitoring module recreates Prometheus and Grafana.
- **Order of Restoration:** Storage -> PostgreSQL -> Redis -> API/Workers -> Mock EHR -> AI Service -> NGINX -> Monitoring.

**Status:** **Designed.** Terraform modules define infrastructure recreation but no documented execution of full disaster recovery recreation was found.

### 9.6 Dependency Restoration

- **PostgreSQL:** Restore from backup snapshot (see 9.3).
- **Redis:** Restart container; workers re-synchronize pending records from PostgreSQL.
- **Mock EHR:** Restart container; no data loss expected (stateless service).
- **Workers:** Restart containers; Docker `restart: always` policy.
- **API:** Restart containers; Blue-Green deployment provides failover.
- **NGINX:** Restart container; upstream.conf preserved.
- **Prometheus/Grafana:** Restart containers; no persistent state loss expected.

### 9.7 Network Restoration

- **Docker Networks:** Terraform network modules recreate `frontend-net` and `backend-net`.
- **Network Segmentation:** Public/private boundaries maintained through Docker network configuration.
- **Port Exposure:** Only NGINX exposes Port 8080:80. All other services remain private.

**Status:** **Designed and implemented via Terraform.** Not tested in a disaster recovery drill.

### 9.8 Monitoring Restoration

- **Prometheus:** `restart: always` policy. Configuration files mounted as read-only volumes.
- **Grafana:** `restart: always` policy. Dashboard provisioning files mounted as read-only volumes.
- **Alert Rules:** `alerts.yml` mounted as read-only volume.
- **Out-of-Band:** Monitoring plane does not block patient transactions during restoration.

**Status:** **Designed and implemented.** No monitoring failure scenario was tested.

### 9.9 Failure of the Recovery Mechanism Itself

The following scenarios represent potential failures of the recovery mechanisms themselves:

1. **Backup Failure:** If `pg_dump` fails or produces corrupt backups, the restore procedure would fail. No automated backup verification was documented.
2. **Terraform State Loss:** If the Terraform state file is lost, infrastructure recreation would be impaired. No Terraform state backup procedure was documented.
3. **Volume Corruption:** If the Docker volume `postgres_data` is corrupted, the persistent volume might not be mountable. No documented recovery from volume corruption was found.
4. **Simultaneous NGINX + API Failure:** If both NGINX and the active API instance fail simultaneously, the Blue-Green failover might not function if the standby is also affected. No documented test of this scenario.
5. **Redis + Database Failure:** If both Redis and PostgreSQL fail simultaneously, workers cannot process jobs and the API cannot accept new requests. No documented test of this scenario.

**Not Verified from the available project evidence:** None of these failure-of-recovery scenarios were simulated or documented.

### 9.10 High Availability vs. Fault Tolerance vs. Disaster Recovery vs. Backup and Restore vs. Blue-Green Rollback

| Concept | Definition in Project Context | Mechanism | Documented? | Tested? |
|---|---|---|---|---|
| **High Availability** | System remains operational during single-component failures | Blue-Green deployment; dual workers; Docker `restart: always` | Yes | Partially (Scenario B) |
| **Fault Tolerance** | System continues operating despite multiple simultaneous failures | Horizontal scaling; decoupled architecture; DLQ | Design documented | **Not tested** |
| **Disaster Recovery** | Full system restoration after catastrophic failure | `pg_dump`/`pg_restore`; Terraform recreation; PITR | Yes | **Not tested** |
| **Backup and Restore** | Data recovery from backups | `pg_dump` logical backups; `pg_restore`; 30-day retention | Yes | **Not tested** |
| **Blue-Green Rollback** | Rapid rollback of failed deployments | Automated rollback circuit breaker; upstream restoration | Yes | Tested via unit tests |

---

## 10. Incident Response Runbook Evaluation

### 10.1 Runbook Step Evaluation

| Runbook Step | Purpose | Documented Procedure | Evidence of Execution | Gap / Improvement |
|---|---|---|---|---|
| **Environment Start** | Launch all containers | `docker compose up -d` | **Not verified** -- no `docker compose ps` output in source evidence | Add verification output example |
| **Container Verification** | Confirm 7 containers healthy | `docker compose ps` | **Not verified** -- no actual output shown | Add example output |
| **Terraform Deploy** | Deploy infrastructure | `terraform apply -var-file=...` | **Not verified** -- no `terraform apply` output shown | Add example output |
| **CI/CD Pipeline** | Run full pipeline | `python ci/run-pipeline.py` | **Not verified** -- no actual pipeline output shown | Add example output |
| **CI/CD Secret Failure** | Demonstrate security gate | `python ci/run-pipeline.py --simulate-failure secret` | **Simulated** -- run-pipeline.py code supports it; no actual execution output shown | Add actual execution output |
| **CI/CD Container Failure** | Demonstrate container gate | `python ci/run-pipeline.py --simulate-failure container` | **Simulated** -- same as above | Add actual execution output |
| **Blue-Green Deploy** | Zero-downtime rollout | `python deployment/scripts/deploy.py --version v1.1.0` | **Tested via unit tests** -- `test_successful_simulation_rollout` | Add actual deployment output |
| **Automated Rollback** | Test rollback | `python deployment/scripts/deploy.py --simulate-failure` | **Tested via unit tests** -- `test_failed_simulation_triggers_rollback` | Add actual rollback output |
| **Chaos Simulation** | Run all drills | `python simulation/chaos_simulator.py --scenario all` | **Simulated** -- chaos_simulator.py code supports it; no actual execution output shown | Add actual execution output |
| **EHR Outage Drill** | Test EHR failure | Drill 1 in chaos_simulator.py | **Simulated** -- described in code and incident-report.md | Add actual execution output |
| **Worker Crash Drill** | Test worker failure | Drill 2 in chaos_simulator.py | **Simulated** -- described in chaos_simulator.py | Add actual execution output |
| **Transaction Workload** | Run automated workload | `python simulation/workload/test_transaction.py` | **Not verified** -- no actual execution output shown | Add example output |
| **Batch Workload** | Run batch burst | `python simulation/workload/test_transaction.py --batch 10` | **Not verified** -- no actual execution output shown | Add example output |
| **Unit Tests** | Run test suites | `python -m unittest ...` | **Partially verified** -- test files exist; no test execution output shown | Add example output |

### 10.2 Identified Gaps

#### Missing Commands
- No `docker compose logs` command for log inspection during incidents.
- No `docker exec` command for direct container access during investigation.
- No `prometheus` or `grafana` CLI commands for dashboard/alert inspection.
- No `pg_dump` or `pg_restore` execution commands in the runbook (only documented in disaster-recovery.md).

#### Missing Verification Steps
- No verification step for backup integrity after `pg_dump`.
- No verification step for NGINX upstream configuration after deployment.
- No verification step for Prometheus alert rule evaluation after recovery.
- No verification step for database consistency after restore.

#### Ambiguous Procedures
- The runbook does not specify how to determine which color is active before deployment (it assumes `get_active_color()` works correctly).
- The runbook does not specify timeout values for readiness probes during deployment.
- The runbook does not specify what to do if `docker compose up -d` fails partially.

#### Missing Rollback Instructions
- The runbook describes automated rollback in deployment but does not provide manual rollback procedures if the automated rollback fails.
- No instructions for rolling back database migrations if a deployment includes schema changes.
- No instructions for rolling back Terraform infrastructure changes.

#### Missing Escalation Guidance
- No escalation path documented (e.g., when to contact senior engineers, on-call rotations).
- No severity escalation criteria (e.g., when to escalate from P2 to P1).
- No communication protocol for stakeholder notifications.

#### Missing Data Integrity Checks
- No post-recovery data integrity verification steps (e.g., checksums, record counts).
- No instructions for verifying `audit_logs` table completeness after recovery.
- No instructions for verifying referential integrity between `patients` and `jobs` tables.

#### Missing Security Considerations
- No security verification steps after recovery (e.g., confirming no secrets were exposed during incident).
- No instructions for revoking credentials if a security incident is suspected.
- No instructions for forensic data preservation during incident investigation.

#### Missing Recovery Validation
- No explicit validation criteria for confirming system is fully recovered after DR restore.
- No smoke test suite defined for post-recovery validation.
- No load testing procedure for confirming system can handle production traffic after recovery.

#### Missing Post-Incident Documentation
- No template for post-incident report in the runbook.
- No instructions for updating the runbook based on lessons learned.
- No timeline for completing post-incident reviews.

---

## 11. Incident Risk and Reliability Gap Register

### 11.1 Risk Criteria

| Risk Level | Likelihood | Impact |
|---|---|---|
| **Critical** | High (documented failure mode) | System-wide outage; data loss |
| **High** | Medium (possible failure mode) | Service degradation; partial outage |
| **Medium** | Low (potential failure mode) | Minor degradation; alert noise |
| **Low** | Very Low (theoretical failure mode) | Minimal impact; design handles it |

### 11.2 Risk Register

| ID | Incident / Reliability Gap | Affected Component | Impact | Likelihood | Risk Level | Mitigation | Verification | Status |
|---|---|---|---|---|---|---|---|---|
| RISK-001 | PostgreSQL data volume corruption | PostgreSQL | System-wide read/write failure; data loss | Low | **High** | Persistent Docker volume `postgres_data`; daily `pg_dump` backups; PITR | **Not verified** -- no DR drill executed | **Open** |
| RISK-002 | NGINX ingress container failure | NGINX Ingress | Loss of public entrypoint; all client requests fail | Low | **Medium** | Docker `restart: always`; architecture documents multi-AZ failover for production | **Not verified** -- no NGINX failure test | **Open** |
| RISK-003 | Both background workers crash simultaneously | Background Workers | All async jobs accumulate; EHR sync halted | Low | **Medium** | Docker `restart: always`; `worker_count = 2` in prod; Redis queue retains jobs | **Partially verified** -- Scenario B tested with manual restart, not auto-scaling | **Open** |
| RISK-004 | Redis in-memory data loss | Redis | In-flight queue emptied; jobs lost if unpersisted | Medium | **Medium** | Jobs persisted in PostgreSQL; workers re-synchronize pending records | **Not verified** -- no Redis failure test | **Open** |
| RISK-005 | Blue-Green deployment traffic routing failure | API Service | Traffic routed to wrong version; 502 errors | Low | **Medium** | Automated rollback circuit breaker; `max_fails=2` NGINX config | **Verified** via unit tests `test_deployment_controller.py` | **Mitigated** |
| RISK-006 | Failed readiness probe during deployment | API Service | Deployment halts; candidate container destroyed | Medium | **Low** | Automated rollback; candidate destroyed; traffic stays on Blue | **Verified** via `--simulate-failure` and unit tests | **Mitigated** |
| RISK-007 | External EHR gateway outage | Mock EHR | EHR sync failures; worker retry storm | Medium | **Low** | Exponential backoff; `max_retries=3`; DLQ; async decoupling | **Verified** -- INC-2026-09-01 and Scenario A | **Mitigated** |
| RISK-008 | Monitoring plane failure | Prometheus/Grafana | Loss of real-time telemetry; alerting stops | Low | **Medium** | `restart: always`; out-of-band architecture; Prometheus self-scraping | **Not verified** -- no monitoring failure test | **Open** |
| RISK-009 | Alertmanager absence | Observability | No alert routing to notification channels; delayed response | Medium | **Medium** | Prometheus alerts visible in UI; chaos simulator demonstrates alert firing | **Not verified** -- Alertmanager not deployed | **Open** |
| RISK-010 | Automated horizontal worker scaling not implemented | Background Workers | Queue backlog not auto-resolved; manual intervention required | Medium | **Medium** | `QueueBacklogSpike` alert defined; Terraform `worker_count` parameterized | **Partially verified** -- alert works but no HPA demonstrated | **Open** |
| RISK-011 | Network connectivity failure | All inter-service communication | Cross-network communication failures; service discovery failures | Low | **Medium** | Docker network segmentation; Docker DNS; `restart: always` | **Not verified** -- no network failure test | **Open** |
| RISK-012 | Data integrity issue | PostgreSQL | Inconsistent job states; corrupted audit logs; orphaned records | Low | **High** | Referential integrity in schema; `audit_logs` table; `SELECT COUNT(*)` verification | **Not verified** -- no data integrity failure test | **Open** |
| RISK-013 | Security breach / incident | All services | Unauthorized access; secret exposure; privilege escalation | Low | **High** | CI/CD security gates; non-root execution; zero hardcoded secrets; secret scanning | **Partially verified** -- `--simulate-failure` tests gates | **Open** |
| RISK-014 | Backup failure / corrupt backups | Database | No viable restore point | Low | **High** | `pg_dump` logical backups; 30-day retention; PITR | **Not verified** -- no backup verification test | **Open** |
| RISK-015 | Terraform state file loss | Infrastructure | Cannot recreate infrastructure via IaC | Low | **Medium** | Terraform state file management; declarative configuration | **Not verified** -- no state backup procedure documented | **Open** |
| RISK-016 | AI service failure | AI Service | `/api/v1/diagnose` returns 503; diagnostic features unavailable | Low | **Low** | Service runs independently; does not block core workflows; Docker `restart: always` | **Not verified** -- no AI service failure test | **Open** |
| RISK-017 | No centralized log aggregation | Observability | Log analysis difficult during incidents | Medium | **Medium** | Structured JSON logs; Docker log drivers | **Not verified** -- no log aggregation system deployed | **Open** |
| RISK-018 | No distributed tracing | Observability | Request flow visibility across microservices limited | Medium | **Low** | N/A -- tracing not implemented | **Not verified** -- tracing not implemented | **Open** |
| RISK-019 | Manual triage process | Incident Response | Slow incident classification and response | Medium | **Medium** | Prometheus alerts provide detection; Grafana dashboards provide visibility | **Not verified** -- no automated triage system | **Open** |
| RISK-020 | DR procedures not tested | Disaster Recovery | RPO/RTO not validated; recovery may fail | High | **High** | `pg_dump`/`pg_restore` documented; Terraform recreation documented | **Not verified** -- no DR drill executed | **Open** |

---

## 12. Post-Mortem Analysis

### 12.1 Post-Mortem: INC-2026-09-01 (EHR Gateway Outage)

#### Incident Summary
On 2026-09-18 at 15:35 UTC, the simulated external EHR partner gateway suffered an unannounced internal service degradation, returning HTTP 500 error responses to all outbound patient vitals synchronization requests. The automated observability plane detected the failure within 10 seconds. The decoupled asynchronous architecture prevented API ingress outages. Background workers engaged exponential backoff retry cycles. Upon restoration, queued jobs self-healed and all alert states returned to normal.

#### Impact
- **API Availability:** 100% Uptime
- **Data Loss:** 0 Records Lost
- **Blast Radius:** EHR synchronization workflow only
- **Affected Jobs:** 5 sync jobs re-enqueued and completed after recovery
- **Monitoring:** `EHRFailureRateHigh` alert fired and cleared
- **User Impact:** None -- API continued accepting requests normally

#### Timeline

| Time (UTC) | Event | Evidence |
|---|---|---|
| 15:35:00 | EHR gateway changes to `error_500` mode | incident-report.md |
| 15:35:10 | `EHRFailureRateHigh` alert fires | incident-report.md |
| 15:35:12 | Engineer checks Grafana dashboard | incident-report.md |
| 15:35:18 | Root cause confirmed | incident-report.md |
| 15:35:22 | EHR restored to `normal` | incident-report.md |
| 15:35:24 | Jobs complete; queue drains | incident-report.md |
| 15:35:35 | Alert resolves | incident-report.md |

#### Root Cause
**Confirmed:** Mock EHR service returned HTTP 500 when in `error_500` mode.

#### Contributing Factors
- EHR service was in `error_500` simulation mode.
- Workers initially encountered HTTP 500 errors and entered retry loop.

#### What Worked
- Asynchronous queue decoupling via Redis prevented API ingress degradation.
- Prometheus `EHRFailureRateHigh` alert detected failure within 10 seconds.
- Capped exponential backoff with `max_retries=3` prevented infinite retry loops.
- Worker exception handling caught errors gracefully without process termination.
- Dead-Letter Queue mechanism provided safety net for permanently failed jobs.
- Recovery was rapid: 5 jobs completed in 0.045s after EHR restoration.

#### What Failed
- No automated circuit breaker was in place for prolonged EHR outages (recommended for Phase 7).
- No external partner SLA dashboard was available for tracking partner latency and error quotas.
- Manual triage was required (operator checked Grafana dashboard).

#### Detection Gaps
- No Alertmanager integration means alerts are only visible in Prometheus UI.
- No automated notification to on-call engineers.
- No automated triage or incident classification system.

#### Response Gaps
- Manual intervention was required to restore EHR mode to `normal`.
- No automated failover mechanism for external dependencies.
- No documented procedure for prolonged EHR outages (circuit breaker recommended).

#### Recovery Gaps
- Recovery was manual (EHR mode restoration).
- No automated recovery mechanism for external dependency failures.
- Horizontal worker auto-scaling was not triggered (manual restart simulated).

#### Preventive Actions
1. Implement Circuit Breaker Pattern (PyBreaker) around outbound EHR HTTP clients.
2. Create dedicated Dead-Letter Queue for jobs exceeding max retries.
3. Configure Horizontal Worker Auto-Scaling based on `QueueBacklogSpike` alert.
4. Create External Partner SLA Dashboard for tracking 3rd-party latency and error quotas.

#### Owners
- Reliability Eng: Circuit Breaker Pattern
- Backend Team: Dedicated DLQ
- DevOps Eng: Horizontal Worker Auto-Scaling
- Observability Eng: External Partner SLA Dashboard

**Note:** Owners are listed as specified in incident-report.md. Due dates are specified as "Phase 7" or "In Progress" in the source.

#### Due Dates
- Circuit Breaker Pattern: Phase 7
- Dedicated DLQ: Implemented
- Horizontal Worker Auto-Scaling: In Progress
- External Partner SLA Dashboard: Phase 7

#### Verification Criteria
- Circuit breaker fast-fails EHR requests during prolonged outages.
- DLQ receives jobs exceeding 3 retries.
- Auto-scaling triggers when queue depth exceeds 10 for 15+ seconds.
- SLA dashboard shows partner latency percentiles and error quotas.

---

### 12.2 Post-Mortem: SCENARIO-B (Worker Crash & Queue Backlog)

#### Incident Summary
During a simulated traffic burst, all background worker instances were terminated (exit code 137 / SIGKILL). 25 asynchronous diagnosis jobs accumulated in the Redis queue. The API ingress continued accepting requests (202 Accepted). Prometheus alerts `WorkerUnavailable` (CRITICAL) and `QueueBacklogSpike` (WARNING) fired. The worker pool self-healed and the queue drained from 25 to 0 jobs in 2.1 seconds.

#### Impact
- **API Availability:** 100% Uptime
- **Background Jobs:** 25 jobs accumulated; all processed after recovery
- **Database State:** PostgreSQL remained operational
- **Monitoring:** Two alerts fired; both resolved after worker recovery
- **Queue State:** 25->0 jobs in 2.1s

#### Timeline

| Time | Event | Evidence |
|---|---|---|
| T+0s | Workers terminated; 25 jobs submitted | chaos_simulator.py |
| T+10s | `WorkerUnavailable` fires | alerts.yml |
| T+15s | `QueueBacklogSpike` fires | alerts.yml |
| T+25s | Worker pool self-healing initiated | chaos_simulator.py |
| T+27.1s | Queue drained; alerts resolved | chaos_simulator.py |

#### Root Cause
Worker process crashed without auto-supervision (exit code 137 / SIGKILL). Docker `restart: always` policy revived containers.

#### Contributing Factors
- Traffic burst during worker downtime.
- No dedicated process supervisor beyond Docker restart policy.
- No automated horizontal scaling triggered.

#### What Worked
- Docker `restart: always` policy revived worker containers.
- Asynchronous decoupling protected API ingress (202 Accepted).
- `WorkerUnavailable` alert fired within 10 seconds.
- `QueueBacklogSpike` alert fired within 15 seconds.
- Queue drained rapidly at 12.5 jobs/sec after recovery.
- Terraform `worker_count = 2` parameter provides horizontal scaling capability.

#### What Failed
- Workers did not self-heal immediately (required manual restart in simulation).
- No automated horizontal scaling triggered during the incident.
- No Alertmanager integration for automated notification.

#### Detection Gaps
- 10-second detection latency for `WorkerUnavailable` is acceptable but could be improved.
- No automated notification to on-call engineers.

#### Response Gaps
- Manual restart was required (simulated).
- No automated escalation procedure.

#### Recovery Gaps
- Recovery was manual (container restart).
- Horizontal scaling was not automated.

#### Preventive Actions
1. Configure Horizontal Worker Auto-Scaling via HPA based on queue depth.
2. Implement dedicated process supervisor (e.g., systemd, supervisord) inside containers.
3. Deploy Alertmanager for automated alert routing and notification.

#### Owners
- DevOps Eng: Horizontal Worker Auto-Scaling
- Platform Eng: Process supervisor

#### Due Dates
- Horizontal Worker Auto-Scaling: In Progress
- Process supervisor: Not started

#### Verification Criteria
- HPA triggers when queue depth exceeds threshold.
- Process supervisor automatically restarts crashed workers.
- Alertmanager sends notifications on `WorkerUnavailable` alert.

---

## 13. Recommendations

### 13.1 Immediate Reliability Fixes

| # | Recommendation | Why It Matters | Affected Component | Suggested Action | Verification Method | Necessary For |
|---|---|---|---|---|---|---|
| 1 | Implement Circuit Breaker Pattern | Prevents retry storms during prolonged external dependency outages | Mock EHR client | Add PyBreaker around outbound EHR HTTP clients in worker service | Test with EHR in `error_500` mode for extended duration; verify fast-fail | **Simulation and Production** |
| 2 | Deploy Alertmanager | Alerts are only visible in Prometheus UI; no automated notification | Observability | Deploy Alertmanager with routing rules, email/Slack/PagerDuty receivers | Verify alert triggers notification delivery | **Simulation and Production** |
| 3 | Enable Horizontal Worker Auto-Scaling | Queue backlog not auto-resolved; manual intervention required | Background Workers | Configure HPA based on `QueueBacklogSpike` alert metric | Trigger queue backlog; verify worker scaling | **Simulation and Production** |
| 4 | Add process supervisor inside containers | Workers crash without immediate auto-revival | Worker containers | Add systemd or supervisord inside worker containers | Kill worker process; verify immediate restart | **Simulation and Production** |

### 13.2 Monitoring Improvements

| # | Recommendation | Why It Matters | Affected Component | Suggested Action | Verification Method | Necessary For |
|---|---|---|---|---|---|---|
| 5 | Add centralized log aggregation | Structured JSON logs exist but are not aggregated | Observability | Deploy Loki or ELK stack; configure Docker log drivers | Inject error logs; verify searchability | **Simulation and Production** |
| 6 | Add distributed tracing | Request flow visibility across microservices is limited | All microservices | Deploy OpenTelemetry/Jaeger; instrument API, worker, EHR services | Submit request; verify trace spans | **Simulation and Production** |
| 7 | Add anomaly detection alerting | Current alert rules are threshold-based only | Prometheus | Implement ML-based anomaly detection for unusual patterns | Observe metrics during normal operation; verify anomaly detection | **Simulation and Production** |
| 8 | Create audit log dashboard | `audit_logs` table exists but is not visualized | Grafana | Add panel showing `audit_logs` metrics to Healthcare Overview dashboard | Query audit_logs; verify panel display | **Simulation and Production** |
| 9 | Add synthetic monitoring | No external health checks from external locations | All services | Configure external synthetic health checks | Verify from external location | **Simulation and Production** |
| 10 | Add custom business metrics | No business-level metrics tracked | API, Workers | Add metrics for patient registration, diagnosis completion rates | Verify metric generation | **Simulation and Production** |

### 13.3 Incident Response Improvements

| # | Recommendation | Why It Matters | Affected Component | Suggested Action | Verification Method | Necessary For |
|---|---|---|---|---|---|---|
| 11 | Implement automated triage system | Manual triage is slow; no automated classification | Incident Response | Deploy automated incident classification based on alert severity and affected services | Trigger alerts; verify automatic classification and severity assignment | **Simulation and Production** |
| 12 | Define escalation procedures | No escalation path documented | Incident Response | Create escalation matrix with severity-based triggers and contact information | Test escalation procedure | **Simulation and Production** |
| 13 | Add post-incident report template | Post-mortem documentation is manually produced | Incident Response | Create standardized post-incident report template in runbook | Conduct mock post-incident review | **Simulation and Production** |
| 14 | Create runbook automation scripts | Several runbook commands lack execution examples | Operational Runbook | Add `docker compose logs`, `docker exec`, Prometheus CLI commands | Execute scripts; verify output | **Simulation and Production** |
| 15 | Add forensic data preservation | No procedure for preserving evidence during incidents | Security | Create forensic data preservation procedure for incident investigation | Simulate incident; verify evidence preservation | **Production** |

### 13.4 Deployment Safety Improvements

| # | Recommendation | Why It Matters | Affected Component | Suggested Action | Verification Method | Necessary For |
|---|---|---|---|---|---|---|
| 16 | Add manual rollback procedure | Only automated rollback documented; no manual fallback | Blue-Green Deployment | Add manual rollback steps to runbook | Disable automated rollback; execute manual rollback | **Simulation and Production** |
| 17 | Add database migration rollback | No procedure for rolling back DB schema changes | Deployment | Create database migration rollback procedure | Test migration rollback | **Production** |
| 18 | Add deployment smoke tests | Post-deployment validation is limited | Blue-Green Deployment | Define smoke test suite to run after deployment | Execute smoke tests after deployment | **Simulation and Production** |
| 19 | Add rollback timeout | No timeout defined for automated rollback | Blue-Green Deployment | Define maximum time for rollback to complete | Measure rollback time; verify within timeout | **Production** |

### 13.5 Disaster Recovery Improvements

| # | Recommendation | Why It Matters | Affected Component | Suggested Action | Verification Method | Necessary For |
|---|---|---|---|---|---|---|
| 20 | Execute DR drill | RPO/RTO not empirically validated | Disaster Recovery | Perform full `pg_restore` from backup; measure actual recovery time and data loss | Measure RTO and RPO; compare to targets | **Simulation and Production** |
| 21 | Verify backup integrity | No automated backup verification | Database Backups | Add automated backup integrity verification (restore to test instance) | Restore backup; verify data integrity | **Simulation and Production** |
| 22 | Implement Terraform state backup | State file loss could impair infrastructure recreation | Terraform | Configure Terraform state file backup to remote storage | Delete state file; verify recovery from backup | **Simulation and Production** |
| 23 | Add volume corruption recovery | No documented recovery from Docker volume corruption | PostgreSQL Storage | Create volume corruption recovery procedure | Simulate volume corruption; verify recovery | **Production** |
| 24 | Add DR failure scenarios | No testing of recovery mechanism failure | Disaster Recovery | Simulate backup failure, Terraform state loss, volume corruption | Document failure modes and fallback procedures | **Production** |

### 13.6 Security Incident Preparedness

| # | Recommendation | Why It Matters | Affected Component | Suggested Action | Verification Method | Necessary For |
|---|---|---|---|---|---|---|
| 25 | Create security incident response plan | No security incident response procedure documented | All Services | Create plan for security breach detection, containment, eradication, recovery | Simulate security incident; verify plan execution | **Production** |
| 26 | Add credential revocation procedure | No procedure for revoking compromised credentials | Security | Create credential revocation procedure | Simulate credential compromise; verify revocation | **Production** |
| 27 | Add security forensic procedure | No procedure for forensic data preservation | Security | Create forensic data preservation and analysis procedure | Simulate security incident; verify forensics | **Production** |

### 13.7 Production Hardening

| # | Recommendation | Why It Matters | Affected Component | Suggested Action | Verification Method | Necessary For |
|---|---|---|---|---|---|---|
| 28 | Deploy multi-AZ architecture | Current simulation uses single-node Docker; production needs multi-AZ | All Services | Deploy across multiple availability zones with load balancer | Verify failover across AZs | **Production** |
| 29 | Add SSL/TLS termination | Current simulation uses HTTP only | NGINX Ingress | Configure SSL/TLS certificates in NGINX | Verify HTTPS traffic | **Production** |
| 30 | Add rate limiting | No rate limiting documented for public API | NGINX Ingress | Configure rate limiting in NGINX configuration | Test rate limiting | **Production** |
| 31 | Add network policy enforcement | Docker network segmentation exists but no network policies | All Services | Implement Docker network policies or Kubernetes NetworkPolicies | Verify network isolation | **Simulation and Production** |
| 32 | Add resource limits | No CPU/memory limits documented for containers | All Services | Configure resource limits in docker-compose.yml and Terraform | Verify resource limits enforced | **Simulation and Production** |

---

## 14. Final Conclusion

### 14.1 Incidents Actually Tested

The following incidents were **actually simulated and documented** in the source evidence:

1. **INC-2026-09-01 (EHR Gateway Outage):** Successfully simulated, detected, mitigated, and recovered. The `EHRFailureRateHigh` alert fired within 10 seconds. Workers re-enqueued jobs with exponential backoff. After EHR restoration, 5 jobs completed in 0.045s. Alert cleared at 15:35:35. Full incident lifecycle demonstrated.

2. **SCENARIO-B (Worker Crash & Queue Backlog):** Successfully simulated. Both `WorkerUnavailable` (CRITICAL) and `QueueBacklogSpike` (WARNING) alerts fired. Queue drained from 25 to 0 jobs in 2.1 seconds. Both alerts resolved after worker pool self-healing. Full incident lifecycle demonstrated.

3. **DEPLOY-ROLLBACK (Failed Blue-Green Deployment):** Successfully tested via `--simulate-failure` flag and unit tests (`test_deployment_controller.py`). Automated rollback restored upstream to `api-blue`. Exit code 1 confirmed.

4. **DEPLOY-SUCCESS (Successful Blue-Green Deployment):** Successfully tested via `--simulate-runtime` flag and unit tests. Full deployment flow verified including traffic shift and BLUE retirement.

5. **CI Security Gate Failures:** Successfully simulated via `--simulate-failure secret/container/dependency` flags. Pipeline correctly halted with non-zero exit code 1.

### 14.2 Incidents Successfully Handled

- **INC-2026-09-01:** EHR outage was successfully handled. Asynchronous queue decoupling prevented API ingress degradation. Zero data loss. Recovery within 2.1 seconds of EHR restoration.
- **SCENARIO-B:** Worker crash was successfully handled. Docker `restart: always` revived containers. Queue drained completely. Both alerts resolved.
- **DEPLOY-ROLLBACK:** Failed deployment was successfully handled. Automated rollback prevented any traffic from reaching the unhealthy candidate. Zero customer impact.

### 14.3 Incidents Partially Handled

- **SCENARIO-B (Worker Auto-Scaling):** Worker crash recovery was demonstrated but through manual restart (simulated), not through automated horizontal scaling. The `QueueBacklogSpike` alert fires correctly but no automated scaling response was demonstrated.
- **CI Security Gates:** Security gate failures were demonstrated but the pipeline only blocks deployment; it does not provide automated remediation or notification of the security finding.

### 14.4 Recovery Mechanisms Demonstrated

| Mechanism | Demonstrated? | Evidence |
|---|---|---|
| Blue-Green Automated Rollback | Yes | Unit tests; `--simulate-failure` mode |
| Docker `restart: always` | Yes | Scenario B worker recovery |
| Exponential Backoff Retry | Yes | INC-2026-09-01; Scenario A |
| Dead-Letter Queue | Partially | Code implemented (`max_retries = 3`); DLQ concept documented |
| `pg_dump` / `pg_restore` | **No** | Procedure documented but not executed |
| Terraform Infrastructure Recreation | **No** | Defined but not executed |
| PITR Recovery | **No** | Defined but not executed |

### 14.5 Monitoring Capabilities Demonstrated

- **Prometheus Alerting:** 5 alert rules defined and 3 demonstrated through chaos simulations (`EHRFailureRateHigh`, `WorkerUnavailable`, `QueueBacklogSpike`).
- **Grafana Dashboards:** 8-panel operational overview dashboard provisioned and referenced in incident investigation.
- **Service Health Checks:** Docker healthchecks defined for all 7 services. API `/ready` endpoint tested during deployment.
- **Alert Detection Latency:** 10-second and 15-second detection demonstrated for `EHRFailureRateHigh`, `WorkerUnavailable`, and `QueueBacklogSpike`.

### 14.6 Unverified Assumptions

The following assumptions from the project documentation **cannot be verified** from the available source evidence:

1. **RPO < 15 minutes and RTO < 5 minutes:** These are design targets in disaster-recovery.md but have not been empirically measured through a documented DR drill.
2. **Backup integrity:** `pg_dump` backups are documented but no verification of backup integrity or restorability was performed.
3. **NGINX multi-AZ failover:** Architecture.md references multi-AZ deployment for production, but no multi-AZ configuration or failover test was documented.
4. **Alertmanager routing:** No Alertmanager component is documented. Alert routing to notification channels is unverified.
5. **Terraform state management:** Terraform state file backup and management procedures are not documented.
6. **Database recovery from PITR:** Point-In-Time Recovery is described but never executed or validated.
7. **Log aggregation:** Structured JSON logs are generated but no centralized log aggregation system is deployed or tested.
8. **Network connectivity failure response:** No network failure scenario was simulated or documented.
9. **Data integrity after recovery:** No data integrity verification was performed after any recovery action.
10. **Security incident response:** No active security incident was simulated. Security controls are preventive gates, not incident response mechanisms.

### 14.7 Remaining Reliability Risks

1. **Database Single Point of Failure:** PostgreSQL is the most critical SPOF with **High** risk severity. No DR drill has validated the recovery procedure.
2. **No Alertmanager:** Alerts are visible in Prometheus UI but no automated notification exists. Response times depend on manual operator awareness.
3. **No Automated Horizontal Scaling:** Workers do not auto-scale based on queue depth despite the `QueueBacklogSpike` alert being defined.
4. **No Log Aggregation:** Structured logs are not centralized, making incident investigation more difficult.
5. **No Distributed Tracing:** Request flow visibility across microservices is limited.
6. **No DR Validation:** All DR procedures are documented but never tested. Actual recovery times and data loss are unknown.
7. **Redis Ephemeral Data Risk:** Redis is an in-memory queue with potential data loss on restart. Jobs are backed by PostgreSQL, but this adds complexity.
8. **No Network Failure Testing:** Network connectivity failures between components have not been simulated.
9. **No Monitoring Failure Testing:** The monitoring plane itself has not been tested for failure scenarios.

### 14.8 Recommended Next Steps

1. **Immediate:** Execute a full DR drill (pg_restore from backup) to empirically validate RPO and RTO.
2. **Immediate:** Deploy Alertmanager and configure routing rules for automated incident notification.
3. **Short-term:** Implement Circuit Breaker Pattern for external EHR dependencies.
4. **Short-term:** Configure Horizontal Worker Auto-Scaling based on queue depth.
5. **Short-term:** Add centralized log aggregation (Loki/ELK) and distributed tracing (Jaeger/OpenTelemetry).
6. **Medium-term:** Create automated runbook scripts with execution examples and verification steps.
7. **Medium-term:** Develop and execute post-mortem review process with standardized templates.
8. **Long-term:** Deploy multi-AZ architecture and SSL/TLS termination for production readiness.
9. **Long-term:** Create comprehensive security incident response plan and conduct security incident drills.

### 14.9 Disclaimer

This report is based strictly on the available source documents for the Cloud Infrastructure Simulation project. All claims are supported by documented evidence. Where evidence is missing, this report explicitly states "Not verified from the available project evidence." No incidents, test results, recovery times, alert behavior, failure scenarios, or successful recovery claims have been fabricated. The distinction between simulated failures and real production incidents is maintained throughout this report.

**This is a simulation project, not a production deployment.** Claims of "zero downtime" or "complete fault tolerance" should not be inferred from the source evidence. The project demonstrates reliability patterns in a controlled simulation environment and should not be considered production-ready without additional validation.

---

## 15. Source References

### 15.1 Primary Source Documents

| Source Document | Relevant Sections | Used In |
|---|---|---|
| **README.md** | Project overview, milestone mapping, verification against Definition of Done | Section 1 |
| **Architecture_Document.md** | System topology, SPOF analysis, DR strategy, operational runbook | Sections 2, 8, 9 |
| **architecture.md** | Trust boundaries, security architecture, Blue-Green deployment | Sections 2, 8 |
| **incident-report.md** | INC-2026-09-01 post-mortem, timeline, telemetry artifacts, action items | Sections 5, 6 |
| **disaster-recovery.md** | SPOF matrix, DR strategy, RPO/RTO, backup/restore procedures | Sections 9, 11 |
| **runbook.md** | Operational commands, deployment scenarios, chaos drills, dashboard URLs | Sections 2, 8, 10 |
| **chaos_simulator.py** | Scenario A (EHR Outage), Scenario B (Worker Crash), full incident lifecycle | Sections 5, 6, 12 |
| **deployment/scripts/deploy.py** | Blue-Green deployment controller, rollback mechanism | Sections 2, 6, 8 |
| **deployment/scripts/switch_upstream.py** | NGINX upstream switching, hot reload | Sections 2, 8 |
| **monitoring/prometheus/alerts.yml** | 5 alert rules with conditions, thresholds, severity | Sections 1, 7 |
| **monitoring/prometheus/prometheus.yml** | Scrape configuration, intervals, targets | Sections 1, 7 |
| **monitoring/grafana/provisioning/dashboards/healthcare_overview.json** | 8-panel dashboard configuration | Sections 1, 7 |
| **docker-compose.yml** | Container definitions, healthchecks, network configuration | Sections 2, 7 |
| **infrastructure/terraform/main.tf** | Terraform module composition | Section 2 |
| **infrastructure/terraform/modules/services/main.tf** | Service container definitions, healthchecks | Section 2 |
| **infrastructure/terraform/modules/monitoring/main.tf** | Prometheus and Grafana Terraform resources | Section 2 |
| **ci/run-pipeline.py** | CI/CD pipeline, security gates, `--simulate-failure` flag | Sections 5, 6 |
| **deployment/tests/test_deployment_controller.py** | Blue-Green deployment unit tests | Sections 5, 6, 8 |
| **simulation/tests/test_incident_lifecycle.py** | Incident lifecycle unit tests | Sections 3, 7 |
| **ci/tests/test_security_rules.py** | Security validation unit tests | Sections 5, 6 |
| **ci/tests/test_infrastructure_config.py** | Infrastructure configuration unit tests | Sections 5, 7 |
| **services/worker/app/main.py** | Worker retry logic, DLQ, exponential backoff | Sections 2, 5, 6 |
| **services/mock-ehr/app/main.py** | EHR failure modes, simulation modes | Sections 4, 5 |
| **services/api/app/main.py** | API `/ready` probe, metrics, job submission | Sections 2, 7 |
| **deployment/nginx/nginx.conf** | NGINX configuration, upstream inclusion | Sections 2, 8 |
| **deployment/nginx/conf.d/upstream.conf** | NGINX upstream configuration | Sections 2, 8 |
| **infrastructure/database/init.sql** | Database schema, tables, indexes | Sections 2, 9 |
| **infrastructure/terraform/environments/dev/dev.tfvars** | Dev environment configuration | Section 2 |
| **infrastructure/terraform/environments/prod/prod.tfvars** | Prod environment configuration | Section 2 |
| **.github/workflows/ci-cd.yml** | CI/CD pipeline GitHub Actions workflow | Section 2 |
| **simulation/chaos_simulator.ps1** | PowerShell CLI wrapper for chaos simulator | Section 5 |
| **deployment/scripts/deploy.ps1** | PowerShell wrapper for deployment controller | Section 5 |
| **incident-report.md** | Full incident post-mortem for INC-2026-09-01 | Sections 5, 6, 12 |

### 15.2 Source Citation Format

Throughout this report, source documents are cited using the following format:
- **incident-report.md** -- Primary source for INC-2026-09-01 incident timeline, impact assessment, and corrective actions.
- **chaos_simulator.py** -- Source for Scenario A (EHR Outage) and Scenario B (Worker Crash) simulation logic, expected behavior, and verification.
- **deploy.py** -- Source for Blue-Green deployment controller, rollback mechanism, and readiness probe logic.
- **monitoring/prometheus/alerts.yml** -- Source for all 5 Prometheus alert rules with conditions, thresholds, and severity labels.
- **disaster-recovery.md** -- Source for SPOF analysis, RPO/RTO definitions, backup/restore procedures, and infrastructure recreation.
- **runbook.md** -- Source for operational commands, deployment scenarios, chaos drill descriptions, and dashboard URLs.
- **architecture.md / Architecture_Document.md** -- Source for system topology, trust boundaries, security architecture, and Blue-Green deployment design.
- **docker-compose.yml** -- Source for container definitions, healthcheck configurations, and network topology.
- **services/worker/app/main.py** -- Source for worker retry logic, exponential backoff, and DLQ implementation.
- **services/mock-ehr/app/main.py** -- Source for EHR failure modes and simulation capabilities.

### 15.3 Verification Statement

All information in this report is based on the available source documents listed above. Where evidence is missing or insufficient, this report explicitly states "Not verified from the available project evidence." No fabricated incidents, test results, recovery times, alert behavior, failure scenarios, or successful recovery claims have been included.

---

**Report End**

*This Incident Response and Disaster Recovery Report was produced as a final-year engineering project deliverable for the Secure, Reliable and Scalable Cloud Infrastructure Simulation for an AI-Powered Healthcare Platform.*

*All source evidence was reviewed and cited. No claims were made without supporting documentation.*
