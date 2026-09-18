# Master Architecture & System Design Document

**Platform:** Simulated AI-Powered Healthcare Cloud Platform  
**Target Duration & Scope:** Production-Style Simulation across Containers, IaC, CI/CD, Observability & Resilience  
**Author / Engineer:** Cloud & DevSecOps Engineering Team  
**Compliance Reference:** Sections 3, 4, 8, 9, 10, 24, 25 of [Project_Requirements.pdf](file:///c:/Users/yadid/OneDrive/Desktop/projects/Cloud-Infra-Simulation-for-HealthCare-Platform/Project_Requirements.pdf)  

---

## 1. System Topology & Primary Architecture

```mermaid
flowchart TB
    subgraph PUBLIC_ZONE["Public Internet & Client Entrypoint"]
        Client[External Clients / Browser / EHR Consumers]
    end

    subgraph INGRESS_LAYER["Ingress Boundary (frontend-net)"]
        Nginx["NGINX Ingress Controller\n(Port 8080:80)\nReverse Proxy & Dynamic Upstream Router"]
    end

    subgraph COMPUTE_LAYER["Application Runtime Boundary (Dual Network)"]
        API_Active["API Service - Active\n(api-blue:8000 / api-green:8000)\nFastAPI Gateway (Non-root)"]
        API_Standby["API Service - Standby\nCandidate Version under /ready probe"]
    end

    subgraph PRIVATE_ZONE["Private Backend Infrastructure (backend-net)"]
        Worker1["Background Worker #1\n(worker-1:9100)\nAsync Consumer & Retry Loop"]
        Worker2["Background Worker #2\n(worker-2:9100)\nHorizontally Scaled"]
        Redis["Redis 7.2 Message Queue\n(redis:6379)\nIn-Memory Buffer"]
        Postgres[("PostgreSQL 16 Database\n(postgres:5432)\nPatients, Jobs, Audit Logs")]
        AIService["AI Inference Service\n(ai-service:8082)\nDiagnostic Simulation"]
        MockEHR["External Mock EHR\n(mock-ehr:8083)\nSimulated Partner Gateway"]
    end

    subgraph OBSERVABILITY_PLANE["Observability & Alerting Plane"]
        Prometheus["Prometheus Server\n(Port 9090)\nScrapes API, Workers, AI, EHR, System"]
        Grafana["Grafana Operational Dashboard\n(Port 3000)\nOperational Overview & SLAs"]
    end

    Client -->|HTTP Port 8080| Nginx
    Nginx -->|Upstream Switcher| API_Active
    Nginx -.->|Standby Probe| API_Standby

    API_Active -->|Enqueues Jobs| Redis
    API_Active -->|Direct Diagnostics| AIService
    API_Active -->|Reads/Writes Records| Postgres

    Worker1 -->|Pulls Jobs| Redis
    Worker2 -->|Pulls Jobs| Redis
    Worker1 -->|Syncs Vitals| MockEHR
    Worker2 -->|Syncs Vitals| MockEHR
    Worker1 -->|Persists State & Audits| Postgres
    Worker2 -->|Persists State & Audits| Postgres

    Prometheus -->|5s Scrapes| API_Active
    Prometheus -->|5s Scrapes| Worker1
    Prometheus -->|5s Scrapes| Worker2
    Prometheus -->|5s Scrapes| AIService
    Prometheus -->|5s Scrapes| MockEHR
    Grafana -->|Datasource Query| Prometheus
```

---

## 2. Trust Boundaries & Network Segmentation

The architecture adheres strictly to the principle of **least privilege and zero unnecessary exposure**:

| Network Zone | Docker Bridge Network | Permitted Services | Exposure to Host / Internet | Rationale |
|---|---|---|---|---|
| **Public Ingress** | `frontend-net` | `healthcare-nginx` | Port `8080:80` | Only the reverse proxy accepts external connections. Encapsulates TLS termination, rate-limiting, and path routing. |
| **Bridges (Gateway)** | `frontend-net` + `backend-net` | `api-blue` / `api-green` | None (Internal only) | The API gateway connects to NGINX via `frontend-net` and securely routes to databases and queues via `backend-net`. |
| **Private Backend** | `backend-net` | `postgres`, `redis`, `worker-1`, `worker-2`, `ai-service`, `mock-ehr`, `prometheus`, `grafana` | **Strictly Blocked** (No host ports bound) | Databases and queues must never receive direct public internet traffic. Isolating them prevents brute force, unauthorized queries, and port scanning. |

### Why is the Database Private?
Healthcare workloads are subject to HIPAA and data protection mandates. Direct database exposure invites automated port scanning, unauthorized credential stuffing, and unmonitored exfiltration. PostgreSQL (`5432`) is only addressable via Docker internal DNS within `backend-net`.

---

## 3. Security Architecture & Identity

1. **Non-Root Execution**:
   Every microservice (`services/api`, `services/worker`, `services/mock-ehr`, `services/ai-service`) is built with an explicit unprivileged user (`RUN adduser -u 10001 -S appuser && USER appuser`). In the event of a remote code execution vulnerability, the attacker cannot modify system binaries or access the host.
2. **Secrets Management**:
   - Zero hardcoded passwords or API tokens exist in version control.
   - Credentials are injected via environment variables at runtime (`.env` or Terraform `*.tfvars`).
   - All secret-bearing configuration files (`.env`, `*.tfvars`, `*.key`) are enforced in [.gitignore](file:///c:/Users/yadid/OneDrive/Desktop/projects/Cloud-Infra-Simulation-for-HealthCare-Platform/.gitignore) and validated by our automated CI/CD secret scanner.
3. **Automated Security Validation Gates (CI/CD)**:
   - Secret scanning catches committed credentials.
   - Container linter blocks Dockerfiles without non-root directives.
   - Network auditor verifies private resources do not expose ports to `0.0.0.0`.

---

## 4. Technology Selection & Trade-Off Analysis

| Technology | Purpose | Problem Solved | Trade-Off & Alternative Considered |
|---|---|---|---|
| **Terraform** | Infrastructure as Code | Parameterized, repeatable multi-environment deployments (`dev` vs `prod`). | *Trade-off:* Adds state file management overhead vs raw Compose, but guarantees declarative drift detection. |
| **NGINX** | Reverse Proxy & Traffic Shifting | Dynamic upstream routing for zero-downtime Blue-Green releases. | *Trade-off:* Requires config file rewrites and reloads vs service mesh (Envoy/Istio), but avoids immense operational complexity. |
| **Redis** | In-Memory Message Broker | Asynchronous decoupling of public API requests from slow external EHR syncs. | *Trade-off:* In-memory broker has potential loss risk under hardware failure compared to Kafka/RabbitMQ, but delivers ultra-low latency and simpler operations. |
| **Prometheus** | Metrics Collection & Alert Engine | Pull-based real-time telemetry and rule evaluation every 5s. | *Trade-off:* Pull architecture requires scrapable endpoints, but eliminates agent installation and complex push gateways. |
| **Grafana** | Operational Visualization | Pre-provisioned dashboards with zero manual configuration. | *Trade-off:* Requires dedicated container, but provides industry-standard executive visibility. |

---

## 5. Deployment & Release Safety (Blue-Green Architecture)

Releases are executed through the automated deployment controller ([deployment/scripts/deploy.py](file:///c:/Users/yadid/OneDrive/Desktop/projects/Cloud-Infra-Simulation-for-HealthCare-Platform/deployment/scripts/deploy.py)):
1. **Standby Spawning**: Standby container (`api-green`) is spun up with the candidate release version.
2. **Readiness Probing**: Container `/ready` probe tests live connections to PostgreSQL and Redis.
3. **Zero-Downtime Traffic Shift**: Upstream is updated in `upstream.conf` and NGINX receives hot reload (`nginx -s reload`). Active client TCP sockets remain open without dropping requests.
4. **Automated Rollback Circuit Breaker**: If candidate readiness fails, rollout halts immediately, the unhealthy container is deleted, and production traffic remains on `api-blue` with zero customer disruption.
.