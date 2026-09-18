"""
Cross-Platform DevSecOps Pipeline Orchestrator
Executes full validation gates:
- Stage 1: Code Syntax & Static Verification
- Stage 2: Unit & Contract Tests
- Stage 3: Automated Secret Detection Gate
- Stage 4: Dockerfile & Container Hardening Security Linter
- Stage 5: Dependency & Network Isolation Audit
- Stage 6: Deployment Gating & Demonstration Verification

Supports simulated failure flags (--simulate-failure [secret|container|dependency])
to satisfy project requirement 12 & 13 (Demonstrating that security failures block release).
"""
import sys
import os
import argparse
import subprocess
import time
from pathlib import Path

# Color styling constants
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def log_stage(stage_num: int, name: str):
    print(f"\n{BOLD}{CYAN}======================================================{RESET}")
    print(f"{BOLD}{CYAN}STAGE {stage_num}: {name}{RESET}")
    print(f"{BOLD}{CYAN}======================================================{RESET}")


def run_stage(title: str, func) -> bool:
    print(f"{BOLD}[*] Executing: {title}...{RESET}")
    start = time.time()
    success, message = func()
    duration = time.time() - start
    if success:
        print(f"{GREEN}[OK] PASSED{RESET} ({duration:.2f}s) - {message}")
        return True
    else:
        print(f"{RED}[FAIL] FAILED{RESET} ({duration:.2f}s) - {message}")
        return False


def stage_syntax_check() -> (bool, str):
    """Compiles all python service files to catch syntax errors."""
    errors = []
    for py_file in ROOT_DIR.glob("**/*.py"):
        if any(p in str(py_file) for p in [".git", "venv", "__pycache__", ".terraform"]):
            continue
        try:
            with open(py_file, "r", encoding="utf-8") as f:
                compile(f.read(), str(py_file), "exec")
        except Exception as e:
            errors.append(f"{py_file}: {e}")

    if errors:
        return False, f"Syntax errors in {len(errors)} file(s): " + "; ".join(errors)
    return True, "All Python microservices and scripts compiled with valid syntax."


def stage_unit_tests() -> (bool, str):
    """Runs the unit and integrity test suites."""
    test_files = [
        "ci/tests/test_security_rules.py",
        "ci/tests/test_infrastructure_config.py"
    ]
    for test_file in test_files:
        cmd = [sys.executable, "-m", "unittest", test_file]
        res = subprocess.run(cmd, cwd=str(ROOT_DIR), capture_output=True, text=True)
        if res.returncode != 0:
            return False, f"Test suite {test_file} failed:\n{res.stderr or res.stdout}"
    return True, "All unit, contract, and infrastructure integrity tests passed."


def stage_secret_scan(simulate_failure: bool = False) -> (bool, str):
    """Scans repository for hardcoded credentials and high-entropy secrets."""
    from ci.security.secret_scanner import scan_directory

    if simulate_failure:
        return False, "SIMULATED FAILURE: Detected unencrypted AWS_ACCESS_KEY_ID in application config. Gate BLOCKED."

    findings = scan_directory(str(ROOT_DIR))
    if findings:
        summary = "\n".join([f"  - [{f['description']}] {f['file']}:{f['line']}" for f in findings[:3]])
        return False, f"Detected {len(findings)} exposed secret(s):\n{summary}"
    return True, "Zero exposed credentials, API keys, or private certificates detected."


def stage_container_lint(simulate_failure: bool = False) -> (bool, str):
    """Lints Dockerfiles for non-root enforcement and tag pinning."""
    from ci.security.dockerfile_linter import lint_all_dockerfiles, SEVERITY_HIGH

    if simulate_failure:
        return False, "SIMULATED FAILURE: Dockerfile missing USER directive. Base image running as root. Gate BLOCKED."

    issues = lint_all_dockerfiles(str(ROOT_DIR))
    highs = [i for i in issues if i["severity"] == SEVERITY_HIGH]
    if highs:
        return False, f"Container hardening violated in {len(highs)} instances."
    return True, f"All Dockerfiles verified non-root (appuser:10001) with safe configurations ({len(issues)} low warnings allowed)."


def stage_dependency_and_isolation(simulate_failure: bool = False) -> (bool, str):
    """Validates network isolation (no public DB/Redis exposure) and dependency risks."""
    from ci.security.dependency_auditor import audit_all

    if simulate_failure:
        return False, "SIMULATED FAILURE: Port 5432 exposed to 0.0.0.0. Gate BLOCKED."

    issues = audit_all(str(ROOT_DIR))
    if issues:
        return False, f"{len(issues)} isolation/dependency issue(s) detected."
    return True, "Database & Redis verified private; zero public port exposures on restricted resources."


def main():
    parser = argparse.ArgumentParser(description="Healthcare Platform DevSecOps CI/CD Pipeline")
    parser.add_argument(
        "--simulate-failure",
        choices=["secret", "container", "dependency"],
        help="Simulate an intentional security vulnerability to demonstrate deployment blocking"
    )
    args = parser.parse_args()

    print(f"\n{BOLD}================================================================{RESET}")
    print(f"{BOLD}  HEALTHCARE CLOUD PLATFORM - DEVSECOPS CI/CD PIPELINE (PHASE 4){RESET}")
    print(f"{BOLD}================================================================{RESET}")
    if args.simulate_failure:
        print(f"{YELLOW}[!] SIMULATION MODE ACTIVE: Injected failure type -> {args.simulate_failure.upper()}{RESET}")

    stages = [
        ("Code Syntax & Static Analysis", 1, lambda: stage_syntax_check()),
        ("Unit & Integrity Tests", 2, lambda: stage_unit_tests()),
        ("Secret Detection Security Gate", 3, lambda: stage_secret_scan(args.simulate_failure == "secret")),
        ("Container Hardening Linter", 4, lambda: stage_container_lint(args.simulate_failure == "container")),
        ("Dependency & Network Isolation Audit", 5, lambda: stage_dependency_and_isolation(args.simulate_failure == "dependency"))
    ]

    for title, num, func in stages:
        log_stage(num, title)
        passed = run_stage(title, func)
        if not passed:
            print(f"\n{RED}{BOLD}================================================================{RESET}")
            print(f"{RED}{BOLD}[!] PIPELINE HALTED: Security/Quality Gate Failed at Stage {num}!{RESET}")
            print(f"{RED}[!] Deployment rejected. Production environments are protected.{RESET}")
            print(f"{RED}{BOLD}================================================================{RESET}\n")
            sys.exit(1)

    print(f"\n{GREEN}{BOLD}================================================================{RESET}")
    print(f"{GREEN}{BOLD}[OK] ALL DEVSECOPS GATES PASSED SUCCESSFULLY!{RESET}")
    print(f"{GREEN}Platform is fully verified and authorized for Blue-Green deployment.{RESET}")
    print(f"{GREEN}{BOLD}================================================================{RESET}\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
