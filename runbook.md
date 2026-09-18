# Operational Runbook & Evaluator Walkthrough Guide

**Platform:** Simulated AI-Powered Healthcare Cloud Platform  
**Target Audience:** Evaluator, Assessor, Cloud Operations Engineers  
**Compliance Reference:** Sections 5, 23, 25, 32 of [Project_Requirements.pdf](file:///c:/Users/yadid/OneDrive/Desktop/projects/Cloud-Infra-Simulation-for-HealthCare-Platform/Project_Requirements.pdf)  

This runbook provides copy-paste commands to start, inspect, validate, stress-test, and recover the simulated cloud environment.

---

## 1. Quick Environment Verification & Start

### Option A: Local Container Orchestration (Docker Compose)
To launch all 7 microservices and data stores with dual-network isolation:
```powershell
# 1. Start all containers in detached mode
docker compose up -d

# 2. Verify all 7 containers are healthy
docker compose ps
```

### Option B: Infrastructure as Code (Terraform)
To deploy using declarative Terraform modules:
```powershell
cd infrastructure/terraform

# Initialize Docker provider
terraform init

# Deploy Development environment (1 worker)
terraform apply -var-file="environments/dev/dev.tfvars" -auto-approve

# Deploy Production environment (2 workers, HA)
terraform apply -var-file="environments/prod/prod.tfvars" -auto-approve

cd ../..
```

---

## 2. DevSecOps CI/CD Pipeline & Security Gates

Execute the full CI/CD validation suite locally or inspect [.github/workflows/ci-cd.yml](file:///c:/Users/yadid/OneDrive/Desktop/projects/Cloud-Infra-Simulation-for-HealthCare-Platform/.github/workflows/ci-cd.yml).

### Standard Pipeline Execution (Clean Pass)
```powershell
python ci/run-pipeline.py
# Or PowerShell wrapper:
.\ci\run-pipeline.ps1
```
*Expected Result:* All 5 stages pass with exit code 0 (`[OK] ALL DEVSECOPS GATES PASSED SUCCESSFULLY!`).

### Security Gate Failure Demonstration (Mandatory Assessment Drill)
Demonstrate that security regressions halt the pipeline and block release:

```powershell
# 1. Injected Secret Leak Simulation:
python ci/run-pipeline.py --simulate-failure secret
# Halts at Stage 3 with non-zero exit code 1.

# 2. Injected Container Vulnerability (Root User) Simulation:
python ci/run-pipeline.py --simulate-failure container
# Halts at Stage 4 with non-zero exit code 1.
```

---

## 3. Zero-Downtime Blue-Green Deployment Controller

Release application updates and test safety rollback mechanisms:

### Scenario 1: Successful Zero-Downtime Rollout (`v1.1.0`)
```powershell
python deployment/scripts/deploy.py --version v1.1.0 --simulate-runtime
# Or PowerShell wrapper:
.\deployment\scripts\deploy.ps1 -Version "v1.1.0" -SimulateRuntime
```
*Expected Flow:*
1. Discovers `BLUE` as active.
2. Spawns candidate `GREEN` container.
3. Probes `/ready` and `/health` until green.
4. Shifts NGINX upstream to `api-green:8000` via hot-reload (`nginx -s reload`).
5. Validates public Ingress traffic on port `8080`.
6. Drains and retires `BLUE`.

### Scenario 2: Unhealthy Release & Automated Rollback
```powershell
python deployment/scripts/deploy.py --version v2.0.0-broken --simulate-failure --simulate-runtime
```
*Expected Flow:*
1. Candidate `GREEN` fails readiness checks (HTTP 500 error).
2. Controller detects the fault before cutover.
3. Controller destroys faulty container and keeps 100% traffic intact on `BLUE`.
4. Process exits with code 1.

---

## 4. Reliability, Chaos & Incident Simulation Drills

Run live failure scenarios through the full operational lifecycle:
$$\text{Failure} \longrightarrow \text{Detection} \longrightarrow \text{Investigation} \longrightarrow \text{Root Cause} \longrightarrow \text{Recovery} \longrightarrow \text{Verification} \longrightarrow \text{Prevention}$$

### Run All Incident Drills
```powershell
python simulation/chaos_simulator.py --scenario all --simulate-runtime
# Or PowerShell wrapper:
.\simulation\chaos_simulator.ps1 -Scenario all
```

* **Drill 1 (EHR Outage)**: Upstream EHR API responds with HTTP 500; Prometheus triggers `EHRFailureRateHigh`; worker employs capped exponential retries; EHR recovers and jobs drain.
* **Drill 2 (Worker Crash)**: Kills all background workers during traffic burst; Prometheus triggers `WorkerUnavailable` and `QueueBacklogSpike`; worker pool is self-healed and scaled; backlog drains from 25 to 0 in 2.1s.

---

## 5. Observability & Dashboard URLs
## 5. End-to-End Asynchronous Job Processing (Automated)

Instead of manual cURL commands, run the dedicated workload automation script:
```powershell
# Run a single transaction: submits job, monitors Redis queue, and waits for worker completion
python simulation/workload/test_transaction.py

# Or run via PowerShell:
.\simulation\workload\test_transaction.ps1

# Run a batch burst of 10 concurrent jobs (tests worker throughput & queue drain):
python simulation/workload/test_transaction.py --batch 10
```

*Expected Output:*
```text
[OK] API Gateway is Ready (http://localhost:8080) - Active Color: BLUE
[+] Job enqueued into Redis: ID = job-5556be51
[*] Polling job status for job_id: job-5556be51...
[OK] Job completed successfully in 0.53s!

Final Operational Telemetry:
  - Worker ID     : 57073b67930c
  - Latency       : 0.03s
  - Retry Count   : 0
  - EHR Sync Data : {'mrn': 'MRN-1001', 'status': 'synchronized', 'patient_id': 'pat-001'}
```

---

## 6. Observability & Dashboard URLs

| Service / Tool | Local URL | Default Credentials | Description |
|---|---|---|---|
| **Public API Gateway (Ingress)** | [http://localhost:8080](http://localhost:8080) | None | Public entrypoint routed via NGINX |
| **Grafana Dashboards** | [http://localhost:3000](http://localhost:3000) | Anonymous Viewer enabled | Operational Overview, Active Workers, Queue Depth |
| **Prometheus Web UI** | [http://localhost:9090](http://localhost:9090) | None | Real-time scrape targets and alert evaluation rules |
| **API Health Probes** | [http://localhost:8080/ready](http://localhost:8080/ready) | None | Verifies DB & Redis backing connections |
| **Mock EHR Health** | [http://localhost:8083/health](http://localhost:8083/health) | None | External EHR dependency status |

---

## 7. Running Unit & Integration Test Suites

Verify all subsystem test suites with a single command:
```powershell
# 1. DevSecOps security rules tests
python -m unittest ci/tests/test_security_rules.py

# 2. Infrastructure configuration & alert integrity tests
python -m unittest ci/tests/test_infrastructure_config.py

# 3. Blue-Green deployment controller state transition tests
python -m unittest deployment/tests/test_deployment_controller.py

# 4. Incident lifecycle and failure mode tests
python -m unittest simulation/tests/test_incident_lifecycle.py
```
