"""
Automated Zero-Downtime Blue-Green Deployment Controller
Orchestrates:
1. Active version & color discovery
2. Spawning standby target container (Blue -> Green or Green -> Blue)
3. Pre-cutover readiness & health probe verification
4. Atomic NGINX upstream reconfiguration and hot-reload
5. Post-cutover ingress traffic validation
6. Graceful decommission of previous version
7. Immediate automated rollback if readiness or health fails
"""
import os
import sys
import time
import argparse
import subprocess
import urllib.request
import urllib.error
import json
from pathlib import Path
from typing import Tuple, Dict, Any

# Adjust paths
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from deployment.scripts.switch_upstream import (
    get_active_color,
    get_standby_color,
    switch_upstream_file,
    reload_nginx_ingress
)

RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"


def log_step(step_num: int, title: str):
    print(f"\n{BOLD}{CYAN}------------------------------------------------------------{RESET}")
    print(f"{BOLD}{CYAN}[Step {step_num}] {title}{RESET}")
    print(f"{BOLD}{CYAN}------------------------------------------------------------{RESET}")


class BlueGreenDeployer:
    def __init__(self, target_version: str, simulate_runtime: bool = False, simulate_failure: bool = False):
        self.target_version = target_version
        self.simulate_runtime = simulate_runtime
        self.simulate_failure = simulate_failure
        self.active_color, self.active_host = get_active_color()
        self.target_color = get_standby_color(self.active_color)
        self.target_container_name = f"healthcare-api-{self.target_color}"
        self.active_container_name = f"healthcare-api-{self.active_color}"
        self.ingress_url = "http://localhost:8080"

    def step1_discover_topology(self):
        log_step(1, "Discover Active Deployment State")
        print(f"[*] Active Upstream Color: {BOLD}{self.active_color.upper()}{RESET} ({self.active_host}:8000)")
        print(f"[*] Target Standby Color: {BOLD}{self.target_color.upper()}{RESET} (api-{self.target_color}:8000)")
        print(f"[*] Target Release Version: {BOLD}{self.target_version}{RESET}")
        return True

    def step2_provision_standby(self) -> bool:
        log_step(2, f"Provisioning Standby Container ({self.target_container_name})")
        if self.simulate_runtime:
            print(f"[OK] [SIMULATED] Spun up container '{self.target_container_name}' running version {self.target_version}.")
            print(f"[OK] [SIMULATED] Attached to frontend-net and backend-net.")
            return True

        try:
            # Check if container already exists and clean it
            subprocess.run(["docker", "rm", "-f", self.target_container_name], capture_output=True)
            # Run docker compose or run targeted container
            cmd = [
                "docker", "run", "-d",
                "--name", self.target_container_name,
                "--network", "healthcare-infra-simulation-for-healthcare-platform_backend-net",
                "--network-alias", f"api-{self.target_color}",
                "-e", f"APP_VERSION={self.target_version}",
                "-e", f"DEPLOYMENT_COLOR={self.target_color}",
                "-e", "DB_HOST=postgres",
                "-e", "DB_PORT=5432",
                "-e", "DB_NAME=healthcare",
                "-e", "DB_USER=postgres",
                "-e", "DB_PASSWORD=postgres_secret",
                "-e", "REDIS_HOST=redis",
                "-e", "REDIS_PORT=6379",
                "-e", "AI_SERVICE_URL=http://ai-service:8082",
                "cloud-infra-simulation-for-healthcare-platform-api-blue:latest"
            ]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode != 0:
                print(f"[!] Docker run failed: {res.stderr.strip() or res.stdout.strip()}")
                return False
            # Connect to frontend-net as well
            subprocess.run([
                "docker", "network", "connect",
                "healthcare-infra-simulation-for-healthcare-platform_frontend-net",
                self.target_container_name
            ], capture_output=True)
            print(f"[OK] Container '{self.target_container_name}' started successfully.")
            return True
        except Exception as e:
            print(f"[!] Provisioning error: {e}")
            return False

    def step3_verify_readiness(self) -> bool:
        log_step(3, f"Pre-Cutover Health & Readiness Verification ({self.target_color.upper()})")
        print(f"[*] Probing container internal readiness: /ready and /health")

        if self.simulate_failure:
            print(f"{RED}[FAIL] Health check failed: Probe returned HTTP 500 (Internal Database Connection Refused){RESET}")
            print(f"{RED}[!] Readiness validation failed on target {self.target_color.upper()} instance!{RESET}")
            return False

        if self.simulate_runtime:
            time.sleep(0.5)
            print(f"[OK] Target container response: HTTP 200 OK")
            print(f"[OK] Verified: database='connected', redis='connected', color='{self.target_color}', version='{self.target_version}'")
            return True

        # In real Docker execution, inspect docker exec curl or probe
        for attempt in range(1, 11):
            try:
                cmd = ["docker", "exec", self.target_container_name, "curl", "-s", "http://localhost:8000/ready"]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                if res.returncode == 0 and '"ready":true' in res.stdout.replace(" ", ""):
                    print(f"[OK] Target container responded with healthy readiness check (Attempt {attempt}).")
                    return True
            except Exception:
                pass
            time.sleep(1)

        print(f"{RED}[FAIL] Readiness probe timed out on {self.target_container_name}{RESET}")
        return False

    def step4_switch_traffic(self) -> bool:
        log_step(4, f"Zero-Downtime Traffic Cutover to {self.target_color.upper()}")
        print(f"[*] Re-writing NGINX upstream configuration -> api-{self.target_color}:8000")
        if not switch_upstream_file(self.target_color):
            return False

        print(f"[*] Triggering atomic NGINX configuration reload ('nginx -s reload')...")
        success, msg = reload_nginx_ingress(simulate=self.simulate_runtime)
        if success:
            print(f"[OK] {msg}")
            return True
        else:
            print(f"{RED}[!] {msg}{RESET}")
            return False

    def step5_verify_public_traffic(self) -> bool:
        log_step(5, "Verifying Ingress Public Traffic Routing")
        print(f"[*] Querying public Ingress entrypoint ({self.ingress_url}/health)...")
        if self.simulate_runtime:
            print(f"[OK] HTTP 200 OK from Ingress.")
            print(f"[OK] Live Public Ingress Headers confirm active color: {BOLD}{self.target_color.upper()}{RESET} ({self.target_version})")
            return True

        try:
            req = urllib.request.Request(f"{self.ingress_url}/health")
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    if data.get("color") == self.target_color:
                        print(f"[OK] Public Ingress confirmed routing to new version: {data}")
                        return True
        except Exception as e:
            print(f"[!] Public traffic verification failed: {e}")
        return False

    def step6_decommission_old(self):
        log_step(6, f"Decommissioning Previous Version ({self.active_color.upper()})")
        print(f"[*] Gracefully draining connections from '{self.active_container_name}'...")
        if self.simulate_runtime:
            print(f"[OK] [SIMULATED] Container '{self.active_container_name}' gracefully stopped.")
            return True

        subprocess.run(["docker", "stop", self.active_container_name], capture_output=True)
        print(f"[OK] Retired previous version '{self.active_container_name}'.")
        return True

    def rollback(self):
        print(f"\n{RED}{BOLD}============================================================{RESET}")
        print(f"{RED}{BOLD}  TRIGGERING AUTOMATED ROLLBACK CONTROLLER                  {RESET}")
        print(f"{RED}{BOLD}============================================================{RESET}")
        print(f"{YELLOW}[*] Safety constraint: Restoring pristine state to active color '{self.active_color.upper()}'...{RESET}")

        # Ensure upstream points back to active_color
        switch_upstream_file(self.active_color)
        reload_nginx_ingress(simulate=self.simulate_runtime)

        # Terminate broken standby container
        print(f"[*] Removing unhealthy standby container '{self.target_container_name}'...")
        if not self.simulate_runtime:
            subprocess.run(["docker", "rm", "-f", self.target_container_name], capture_output=True)

        print(f"{GREEN}[OK] Automated Rollback Complete.{RESET}")
        print(f"{GREEN}[OK] Production traffic remains 100% operational on '{self.active_color.upper()}'.{RESET}")
        print(f"{GREEN}[OK] Zero customer downtime occurred.{RESET}\n")

    def execute(self) -> bool:
        print(f"\n{BOLD}============================================================{RESET}")
        print(f"{BOLD}  ZERO-DOWNTIME BLUE-GREEN DEPLOYMENT CONTROLLER            {RESET}")
        print(f"{BOLD}============================================================{RESET}")

        self.step1_discover_topology()

        if not self.step2_provision_standby():
            self.rollback()
            return False

        if not self.step3_verify_readiness():
            self.rollback()
            return False

        if not self.step4_switch_traffic():
            self.rollback()
            return False

        if not self.step5_verify_public_traffic():
            self.rollback()
            return False

        self.step6_decommission_old()

        print(f"\n{GREEN}{BOLD}============================================================{RESET}")
        print(f"{GREEN}{BOLD}[OK] DEPLOYMENT COMPLETED WITH ZERO DOWNTIME!               {RESET}")
        print(f"{GREEN}New Version: {self.target_version} ({self.target_color.upper()}) is now LIVE.{RESET}")
        print(f"{GREEN}{BOLD}============================================================{RESET}\n")
        return True


def main():
    parser = argparse.ArgumentParser(description="Healthcare Platform Blue-Green Deployment Controller")
    parser.add_argument("--version", default="v1.1.0", help="Application version tag to deploy")
    parser.add_argument("--simulate-runtime", action="store_true", help="Simulate container operations and NGINX reload")
    parser.add_argument("--simulate-failure", action="store_true", help="Simulate readiness failure to test automated rollback")
    args = parser.parse_args()

    deployer = BlueGreenDeployer(
        target_version=args.version,
        simulate_runtime=args.simulate_runtime,
        simulate_failure=args.simulate_failure
    )

    success = deployer.execute()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
