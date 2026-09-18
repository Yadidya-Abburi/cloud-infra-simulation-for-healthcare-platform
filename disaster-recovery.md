# Disaster Recovery, Resilience & Failure Analysis

**Platform:** Simulated AI-Powered Healthcare Cloud Platform  
**Compliance Reference:** Sections 14, 19, 20, 22 of [Project_Requirements.pdf](file:///c:/Users/yadid/OneDrive/Desktop/projects/Cloud-Infra-Simulation-for-HealthCare-Platform/Project_Requirements.pdf)  

---

## 1. Single Point of Failure (SPOF) Analysis & Resilience Matrix

| Component | Failure Mode | System Impact | Mitigation / Built-In Resilience | Risk Severity |
|---|---|---|---|:---:|
| **NGINX Ingress** | Container crash or process failure | Loss of public entrypoint; external clients receive connection refused | Docker `restart: always`. In high-availability production, pair with AWS ALB or DNS failover across multi-AZ instances. | Medium |
| **API Service** | Container crash, memory leak, unhandled 500s | Degradation of customer requests | Blue-Green dual deployment. If one instance fails, NGINX `max_fails=2` fails over to the standby instance. Docker healthchecks restart dead containers. | Low |
| **Background Worker** | Unhandled exception or OOM crash | Asynchronous jobs accumulate in Redis queue | Horizontal scaling (`worker_count = 2`). Decoupled queue retains all jobs. Prometheus alert `WorkerUnavailable` fires within 10s. | Low |
| **PostgreSQL Database** | Corrupted data volume or container crash | Read/write transactions fail; API `/ready` probe returns 503 | Persistent Docker volume `postgres_data` preserves data across crashes. Automated daily snapshots and point-in-time recovery (PITR) strategy. | High |
| **Redis Message Queue** | In-memory crash or node restart | In-flight queue emptied if unpersisted | Ephemeral job buffer; jobs originate from DB records in state `pending`. On restart, workers re-synchronize pending records. | Medium |
| **Mock EHR Gateway** | Upstream partner timeout / HTTP 500 | Outbound vitals sync rejected | Capped exponential retry loop (`max_retries = 3`). Dead-Letter Queue (DLQ). Upstream outage does **not** degrade API ingress. | Low |
| **Prometheus / Monitoring** | Scraper crash or memory exhaustion | Loss of real-time telemetry; alerting engine stops evaluating | Observability plane is out-of-band and does not block patient transactions. Docker `restart: always` restores scraping. | Low |

---

## 2. Backup & Disaster Recovery (DR) Strategy

### Recovery Objectives
* **Recovery Point Objective (RPO):** < 15 minutes (Maximum acceptable data loss window).
* **Recovery Time Objective (RTO):** < 5 minutes (Maximum time to restore full platform availability).

### Database Backup & Restore Procedures

#### 1. Automated Scheduled Logical Backup (`pg_dump`)
A lightweight cron container or automated host task takes periodic encrypted snapshots of the `healthcare` database:
```bash
# Automated snapshot command
docker exec healthcare-postgres pg_dump -U postgres -d healthcare -F c -b -v -f /tmp/backup.dump

# Copy out to offsite encrypted storage (e.g. S3 / Cloud Storage with 30-day lifecycle retention)
docker cp healthcare-postgres:/tmp/backup.dump ./backups/healthcare_$(date +%Y%m%d_%H%M%S).dump
```

#### 2. Disaster Recovery / Point-In-Time Restoration Procedure
If the persistent volume is accidentally deleted or corrupted:
1. **Recreate Storage Volume via Terraform**:
   ```bash
   terraform apply -target=module.storage
   ```
2. **Reinitialize PostgreSQL Container**:
   ```bash
   docker compose up -d postgres
   ```
3. **Restore from Latest Verified Snapshot**:
   ```bash
   docker cp ./backups/latest_verified.dump healthcare-postgres:/tmp/restore.dump
   docker exec healthcare-postgres pg_restore -U postgres -d healthcare --clean --if-exists /tmp/restore.dump
   ```
4. **Verify Table Consistency**:
   ```bash
   docker exec healthcare-postgres psql -U postgres -d healthcare -c "SELECT COUNT(*) FROM patients; SELECT COUNT(*) FROM jobs;"
   ```

---

## 3. Infrastructure Recreation vs State Recovery

A resilient cloud engineering posture differentiates between **ephemeral compute** and **persistent state**:

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        DISASTER EVENT (TOTAL NODE LOSS)                │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
          ┌─────────────────────────┴─────────────────────────┐
          ▼                                                   ▼
  [ RECREATE INFRASTRUCTURE ]                       [ RECOVER PERSISTENT STATE ]
  • Fully automated via Terraform                   • Restore latest DB snapshot
  • Network bridges regenerated                     • Replay PostgreSQL WAL logs
  • Containers rebuilt from images                  • Verify cryptographic hashes
  • Ingress, Prometheus, Grafana reset              • RPO < 15 min / RTO < 5 min
```

---

## 4. Cloud Cost Awareness & Optimization Analysis

Even within a simulated environment, a production cloud engineer must design for cost efficiency, avoiding unnecessary overprovisioning:

| Architectural Component | High Cost Risk Area | Cost Optimization Strategy |
|---|---|---|
| **API & Worker Compute** | Overprovisioning fixed EC2/VM instances 24/7 | **Autoscaling:** Baseline small footprint (1 worker in dev, 2 in prod). Scale worker containers horizontally only when queue depth exceeds threshold (`max(worker_queue_depth) > 10`). |
| **Database Hosting** | Over-allocating IOPS and multi-region replication | **Tiered Storage:** Use single-AZ RDS for dev with automated automated backups; Reserve Multi-AZ Aurora only for production tier where 99.99% availability is contractual. |
| **Observability & Logging** | Storing raw debug metrics and high-volume access logs indefinitely | **Retention & Aggregation:** Limit Prometheus metric retention to 15 days on fast NVMe; compress older logs into S3 Glacier with a 30-day lifecycle transition. |
| **Network Egress** | Inter-region data transfer between services | **VPC Locality:** Keep API, workers, Redis, and database within the same Virtual Private Cloud (VPC) / Availability Zone to incur zero inter-region data transfer fees. |
