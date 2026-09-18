# Secure, Reliable & Scalable Cloud Infrastructure Simulation for an AI Healthcare Platform

[![DevSecOps CI/CD](https://github.com/organization/healthcare-platform/actions/workflows/ci-cd.yml/badge.svg)](.github/workflows/ci-cd.yml)
[![Docker](https://img.shields.io/badge/Docker-Containers-blue.svg)](docker-compose.yml)
[![Terraform](https://img.shields.io/badge/Terraform-IaC-purple.svg)](infrastructure/terraform)
[![Prometheus](https://img.shields.io/badge/Prometheus-v2.50-orange.svg)](monitoring/prometheus)
[![Grafana](https://img.shields.io/badge/Grafana-v10.3-brightgreen.svg)](monitoring/grafana)

An end-to-end, production-style cloud engineering and operations simulation designed to run a secure, resilient, observable, and scalable healthcare platform.

Developed in compliance with **[Project_Requirements.pdf](file:///c:/Users/yadid/OneDrive/Desktop/projects/Cloud-Infra-Simulation-for-HealthCare-Platform/Project_Requirements.pdf)** (Product Owner: AI.Prof).

---

## 🏛️ System Architecture

```text
       ┌────────────────────────────────────────────────────────┐
       │             PUBLIC INGRESS (Port 8080:80)              │
       │           NGINX Reverse Proxy (frontend-net)           │
       └───────────────────────────┬────────────────────────────┘
                                   │
                    Dynamic upstream.conf (Active: api-blue)
                                   │
                 ┌─────────────────┴─────────────────┐
                 ▼                                   ▼
        [ API (Active: BLUE) ]              [ API (Standby: GREEN) ]
        • Port 8000 (Non-root)              • Under /ready probing
                 │                                   │
  ═══════════════╪═══════════════════════════════════╪════════════════ (Trust Boundary)
                 │         PRIVATE BACKEND NETWORK   │
                 ▼              (backend-net)        ▼
      ┌──────────────────────┬──────────────────────┬──────────────────────┐
      ▼                      ▼                      ▼                      ▼
 [ PostgreSQL 16 ]      [ Redis 7.2 ]       [ Background Workers ]   [ AI Inference ]
 Port 5432 (Isolated)   Port 6379 (Queue)   worker-1 & worker-2      ai-service:8082
      ▲                      ▲                      │                      ▲
      │                      │                      ▼                      │
      └──────────────────────┴──────────────▶ [ Mock External EHR ]        │
                                              mock-ehr:8083                │
                                                                           │
  ═════════════════════════════════════════════════════════════════════════╪════
                                   ▲                                       │
                                   │ 5s Scrape Topography                  │
                     ┌─────────────┴─────────────┐                         │
                     ▼                           ▼                         │
             [ Prometheus 9090 ]        [ Grafana Dashboard 3000 ] ────────┘
             • 5 Alerting Rules         • Operational Overview
```

---

## 📋 Comprehensive Deliverables & Milestone Mapping

| Phase | Domain | Status | Key Deliverable Files |
|---|---|:---:|---|
| **Phase 1** | **Application Simulation & Docker Orchestration** | **Completed** ✅ | [docker-compose.yml](file:///c:/Users/yadid/OneDrive/Desktop/projects/Cloud-Infra-Simulation-for-HealthCare-Platform/docker-compose.yml), [`services/`](file:///c:/Users/yadid/OneDrive/Desktop/projects/Cloud-Infra-Simulation-for-HealthCare-Platform/services), [phase1-report.md](file:///c:/Users/yadid/OneDrive/Desktop/projects/Cloud-Infra-Simulation-for-HealthCare-Platform/phase1-report.md) |
| **Phase 2** | **Infrastructure as Code (IaC) via Terraform** | **Completed** ✅ | [`infrastructure/terraform`](file:///c:/Users/yadid/OneDrive/Desktop/projects/Cloud-Infra-Simulation-for-HealthCare-Platform/infrastructure/terraform) (`dev`/`prod` tfvars), [phase2-report.md](file:///c:/Users/yadid/OneDrive/Desktop/projects/Cloud-Infra-Simulation-for-HealthCare-Platform/phase2-report.md) |
| **Phase 3** | **Observability Plane (Prometheus & Grafana)** | **Completed** ✅ | [`monitoring/`](file:///c:/Users/yadid/OneDrive/Desktop/projects/Cloud-Infra-Simulation-for-HealthCare-Platform/monitoring) (5 alert rules, automated dashboard), [phase3-report.md](file:///c:/Users/yadid/OneDrive/Desktop/projects/Cloud-Infra-Simulation-for-HealthCare-Platform/phase3-report.md) |
| **Phase 4** | **DevSecOps CI/CD & Automated Security Gates** | **Completed** ✅ | [ci/run-pipeline.py](file:///c:/Users/yadid/OneDrive/Desktop/projects/Cloud-Infra-Simulation-for-HealthCare-Platform/ci/run-pipeline.py), [ci/security/](file:///c:/Users/yadid/OneDrive/Desktop/projects/Cloud-Infra-Simulation-for-HealthCare-Platform/ci/security), [.github/workflows/ci-cd.yml](file:///c:/Users/yadid/OneDrive/Desktop/projects/Cloud-Infra-Simulation-for-HealthCare-Platform/.github/workflows/ci-cd.yml), [phase4-report.md](file:///c:/Users/yadid/OneDrive/Desktop/projects/Cloud-Infra-Simulation-for-HealthCare-Platform/phase4-report.md) |
| **Phase 5** | **Zero-Downtime Blue-Green Deployment Controller** | **Completed** ✅ | [deployment/scripts/deploy.py](file:///c:/Users/yadid/OneDrive/Desktop/projects/Cloud-Infra-Simulation-for-HealthCare-Platform/deployment/scripts/deploy.py), [deployment/scripts/switch_upstream.py](file:///c:/Users/yadid/OneDrive/Desktop/projects/Cloud-Infra-Simulation-for-HealthCare-Platform/deployment/scripts/switch_upstream.py), [phase5-report.md](file:///c:/Users/yadid/OneDrive/Desktop/projects/Cloud-Infra-Simulation-for-HealthCare-Platform/phase5-report.md) |
| **Phase 6** | **Reliability, Chaos & Incident Response** | **Completed** ✅ | [simulation/chaos_simulator.py](file:///c:/Users/yadid/OneDrive/Desktop/projects/Cloud-Infra-Simulation-for-HealthCare-Platform/simulation/chaos_simulator.py), [incident-report.md](file:///c:/Users/yadid/OneDrive/Desktop/projects/Cloud-Infra-Simulation-for-HealthCare-Platform/incident-report.md), [phase6-report.md](file:///c:/Users/yadid/OneDrive/Desktop/projects/Cloud-Infra-Simulation-for-HealthCare-Platform/phase6-report.md) |
| **Phase 7** | **Master Architecture & Evaluator Runbook** | **Completed** ✅ | [architecture.md](file:///c:/Users/yadid/OneDrive/Desktop/projects/Cloud-Infra-Simulation-for-HealthCare-Platform/architecture.md), [disaster-recovery.md](file:///c:/Users/yadid/OneDrive/Desktop/projects/Cloud-Infra-Simulation-for-HealthCare-Platform/disaster-recovery.md), [runbook.md](file:///c:/Users/yadid/OneDrive/Desktop/projects/Cloud-Infra-Simulation-for-HealthCare-Platform/runbook.md), [phase7-report.md](file:///c:/Users/yadid/OneDrive/Desktop/projects/Cloud-Infra-Simulation-for-HealthCare-Platform/phase7-report.md) |

---

## 🎯 Verification Against Section 33 (Definition of Done)

| Area | Requirement | Implementation Evidence | Status |
|---|---|---|:---:|
| **Infrastructure** | Defined as code, reproducible, re-creatable | Modular Terraform (`modules/network`, `storage`, `services`, `monitoring`) + Compose | **DONE** ✅ |
| **Networking** | Public/private boundaries, no unnecessary exposure | Dual bridges (`frontend-net` vs `backend-net`); DB & Redis private (no host port maps) | **DONE** ✅ |
| **Security** | No hard-coded secrets; restricted access; automated validation | `secret_scanner.py`, `dockerfile_linter.py`, `dependency_auditor.py` in CI/CD pipeline | **DONE** ✅ |
| **Containers** | Non-root execution; minimal attack surface | Every microservice enforces `USER appuser:10001` with multi-stage builds | **DONE** ✅ |
| **CI/CD** | Pipeline with testing, security, health verification | `ci/run-pipeline.py` & `.github/workflows/ci-cd.yml` with 5 automated gates | **DONE** ✅ |
| **Deployment** | Controlled, zero-downtime, automated rollback | `deploy.py` hot-reloads NGINX upstreams; auto-rolls back if candidate checks fail | **DONE** ✅ |
| **Reliability** | Tolerates worker, queue, and external EHR failures | Capped exponential retry backoff, DLQ, and dual worker pools | **DONE** ✅ |
| **Observability** | Logs, metrics, dashboards, actionable alerts | Prometheus (5 alert rules) + pre-provisioned Grafana operational overview | **DONE** ✅ |
| **Recovery** | Documented DR & backup approach | [disaster-recovery.md](file:///c:/Users/yadid/OneDrive/Desktop/projects/Cloud-Infra-Simulation-for-HealthCare-Platform/disaster-recovery.md) (RPO < 15m, RTO < 5m, pg_dump & PITR) | **DONE** ✅ |
| **Auditability** | Operational & deployment actions traceable | JSON structured audit logs in PostgreSQL `audit_logs` table | **DONE** ✅ |
| **Documentation** | Architecture, security, reliability, incident post-mortem | [architecture.md](file:///c:/Users/yadid/OneDrive/Desktop/projects/Cloud-Infra-Simulation-for-HealthCare-Platform/architecture.md), [incident-report.md](file:///c:/Users/yadid/OneDrive/Desktop/projects/Cloud-Infra-Simulation-for-HealthCare-Platform/incident-report.md), [disaster-recovery.md](file:///c:/Users/yadid/OneDrive/Desktop/projects/Cloud-Infra-Simulation-for-HealthCare-Platform/disaster-recovery.md) | **DONE** ✅ |
| **Demonstration** | Reproducible simulation scenarios | Fully scripted CLI in [runbook.md](file:///c:/Users/yadid/OneDrive/Desktop/projects/Cloud-Infra-Simulation-for-HealthCare-Platform/runbook.md) and `chaos_simulator.py` | **DONE** ✅ |

---

## 🚀 Quick Start & Demonstration

Please refer to the **[Operational Runbook (runbook.md)](file:///c:/Users/yadid/OneDrive/Desktop/projects/Cloud-Infra-Simulation-for-HealthCare-Platform/runbook.md)** for detailed step-by-step commands:

```powershell
# 1. Run full DevSecOps CI/CD Pipeline
python ci/run-pipeline.py

# 2. Demonstrate Automated Deployment Blocking on Security Vulnerability
python ci/run-pipeline.py --simulate-failure secret

# 3. Trigger Zero-Downtime Blue-Green Deployment
python deployment/scripts/deploy.py --version v1.1.0 --simulate-runtime

# 4. Trigger Chaos Simulation Drill (EHR Outage & Worker Crash)
python simulation/chaos_simulator.py --scenario all --simulate-runtime

# 5. Run All Automated Test Suites
python -m unittest ci/tests/test_security_rules.py
python -m unittest ci/tests/test_infrastructure_config.py
python -m unittest deployment/tests/test_deployment_controller.py
python -m unittest simulation/tests/test_incident_lifecycle.py
```
