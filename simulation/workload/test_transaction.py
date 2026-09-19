"""
Automated Asynchronous Transaction Runner & Workload Generator
Submits jobs to the healthcare API ingress, monitors queue lifecycle,
polls for worker processing results, and displays operational telemetry.
"""
import sys
import time
import json
import argparse
import urllib.request
import urllib.error

RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"


def check_api_ready(base_url: str) -> bool:
    """Verifies that the Ingress and API are reachable and ready."""
    try:
        req = urllib.request.Request(f"{base_url}/ready")
        with urllib.request.urlopen(req, timeout=4) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                print(f"{GREEN}[OK] API Gateway is Ready ({base_url}) - Active Color: {data.get('color', 'unknown').upper()}{RESET}")
                return True
    except Exception as e:
        print(f"{RED}[FAIL] Could not connect to API Gateway at {base_url}/ready: {e}{RESET}")
        return False
    return False


def submit_job(base_url: str, patient_id: str, job_type: str) -> dict:
    """Submits an asynchronous job via Ingress."""
    payload = json.dumps({
        "patient_id": patient_id,
        "job_type": job_type,
        "payload": {"source": "automated_workload_generator"}
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{base_url}/api/v1/jobs",
        data=payload,
        headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status in [200, 201, 202]:
                return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"{RED}[!] Job submission failed: {e}{RESET}")
    return {}


def poll_job_status(base_url: str, job_id: str, max_wait_sec: int = 15) -> dict:
    """Polls the API until the job reaches 'completed' or 'failed'."""
    print(f"[*] Polling job status for job_id: {BOLD}{job_id}{RESET}...")
    start_time = time.time()

    while time.time() - start_time < max_wait_sec:
        try:
            req = urllib.request.Request(f"{base_url}/api/v1/jobs/{job_id}")
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    status = data.get("status")

                    if status == "completed":
                        elapsed = time.time() - start_time
                        print(f"{GREEN}[OK] Job completed successfully in {elapsed:.2f}s!{RESET}")
                        return data
                    elif status == "failed":
                        print(f"{RED}[FAIL] Job marked failed: {data.get('error_message')}{RESET}")
                        return data
                    elif status in ["processing", "pending", "retrying"]:
                        print(f"    - Current state: {YELLOW}{status.upper()}{RESET} (attempt {data.get('retry_count', 0) + 1})...")
        except Exception:
            pass

        time.sleep(0.5)

    print(f"{RED}[!] Polling timed out after {max_wait_sec} seconds.{RESET}")
    return {}


def run_single_transaction(base_url: str, patient_id: str, job_type: str):
    print(f"\n{BOLD}{CYAN}============================================================{RESET}")
    print(f"{BOLD}{CYAN}  SUBMITTING ASYNCHRONOUS TRANSACTION                       {RESET}")
    print(f"{BOLD}{CYAN}============================================================{RESET}")
    print(f"[*] Patient ID : {patient_id}")
    print(f"[*] Job Type   : {job_type}")

    job_info = submit_job(base_url, patient_id, job_type)
    if not job_info:
        print(f"{RED}[!] Could not submit job. Aborting.{RESET}")
        return False

    job_id = job_info.get("job_id") or job_info.get("id")
    print(f"{GREEN}[+] Job enqueued into Redis: ID = {job_id}{RESET}")

    final_result = poll_job_status(base_url, job_id)
    if final_result and final_result.get("status") == "completed":
        print(f"\n{BOLD}Final Operational Telemetry:{RESET}")
        result_payload = final_result.get("result", {})
        print(f"  - Worker ID     : {result_payload.get('processed_by', 'worker')}")
        print(f"  - Latency       : {result_payload.get('latency_seconds', 'N/A')}s")
        print(f"  - Retry Count   : {final_result.get('retry_count', 0)}")
        print(f"  - EHR Sync Data : {result_payload.get('ehr_sync', {})}")
        print(f"\n{BOLD}{CYAN}[INFO] To manually clear all jobs, run:{RESET}")
        print("  docker exec healthcare-redis redis-cli FLUSHALL")
        print('  docker exec healthcare-postgres psql -U postgres -d healthcare -c "TRUNCATE jobs;"')
        return True
    return False


def run_batch_burst(base_url: str, count: int, job_type: str):
    print(f"\n{BOLD}{YELLOW}============================================================{RESET}")
    print(f"{BOLD}{YELLOW}  GENERATING BATCH BURST WORKLOAD ({count} JOBS)            {RESET}")
    print(f"{BOLD}{YELLOW}============================================================{RESET}")

    job_ids = []
    start_time = time.time()

    seed_patients = ["pat-001", "pat-002", "pat-003"]
    for i in range(1, count + 1):
        pid = seed_patients[(i - 1) % len(seed_patients)]
        job_info = submit_job(base_url, pid, job_type)
        jid = job_info.get("job_id") or job_info.get("id")
        if jid:
            job_ids.append(jid)
        sys.stdout.write(f"\r[*] Enqueued: {len(job_ids)}/{count} jobs...")
        sys.stdout.flush()

    enqueue_elapsed = time.time() - start_time
    print(f"\n{GREEN}[+] Batch submission finished in {enqueue_elapsed:.2f}s ({len(job_ids)} jobs in queue).{RESET}")

    print(f"[*] Waiting for workers to drain the queue...")
    completed = 0
    start_poll = time.time()

    while len(job_ids) > 0 and (time.time() - start_poll < 30):
        remaining = []
        for jid in job_ids:
            try:
                req = urllib.request.Request(f"{base_url}/api/v1/jobs/{jid}")
                with urllib.request.urlopen(req, timeout=2) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        if data.get("status") == "completed":
                            completed += 1
                        else:
                            remaining.append(jid)
            except Exception:
                remaining.append(jid)

        job_ids = remaining
        sys.stdout.write(f"\r[*] Progress: {completed}/{count} jobs completed...")
        sys.stdout.flush()
        if not job_ids:
            break
        time.sleep(0.5)

    drain_elapsed = time.time() - start_poll
    print(f"\n{GREEN}{BOLD}[OK] Batch burst drained: {completed}/{count} jobs completed in {drain_elapsed:.2f}s!{RESET}\n")
    print(f"{BOLD}{CYAN}[INFO] To manually clear all jobs, run:{RESET}")
    print("  docker exec healthcare-redis redis-cli FLUSHALL")
    print('  docker exec healthcare-postgres psql -U postgres -d healthcare -c "TRUNCATE jobs;"\n')
    return completed == count


def main():
    parser = argparse.ArgumentParser(description="Healthcare Platform Asynchronous Transaction Runner")
    parser.add_argument("--url", default="http://localhost:8080", help="Base URL of Ingress Gateway")
    parser.add_argument("--patient-id", default="pat-001", help="Patient Identifier")
    parser.add_argument("--job-type", default="ehr_sync", help="Type of job (e.g. ehr_sync)")
    parser.add_argument("--batch", type=int, default=1, help="Number of concurrent jobs to submit (batch burst)")
    args = parser.parse_args()

    if not check_api_ready(args.url):
        sys.exit(1)

    if args.batch > 1:
        success = run_batch_burst(args.url, args.batch, args.job_type)
    else:
        success = run_single_transaction(args.url, args.patient_id, args.job_type)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
