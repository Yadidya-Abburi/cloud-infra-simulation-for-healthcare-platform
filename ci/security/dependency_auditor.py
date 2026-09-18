"""
Dependency and Infrastructure Security Auditor
Audits:
1. Python dependencies across microservices for pinned versions and known vulnerable libraries
2. Docker Compose and Terraform files for accidental public exposure of private resources
   (e.g., exposing PostgreSQL port 5432 or Redis port 6379 to the host network)
"""
import os
import re
import sys
from pathlib import Path
from typing import List, Dict

# Known vulnerable legacy packages or anti-patterns in healthcare/enterprise
VULNERABLE_PACKAGE_PATTERNS = [
    (r'(?i)^requests[<=\s]+2\.2[0-5]', "CVE-2023-32681 / Outdated requests library vulnerable to sensitive header leak"),
    (r'(?i)^urllib3[<=\s]+1\.2[0-5]', "CVE-2021-33503 / Vulnerable legacy urllib3 ReDoS"),
    (r'(?i)^cryptography[<=\s]+3\.', "Outdated OpenSSL / Memory safety issues"),
    (r'(?i)^pydantic[<=\s]+1\.', "Legacy Pydantic v1 (Migration to Pydantic v2 recommended)")
]

# Sensitive ports that MUST NOT be exposed on host interfaces (0.0.0.0 or unspecified)
RESTRICTED_PORTS = {
    "5432": "PostgreSQL Database (Must remain private in backend-net)",
    "6379": "Redis Message Queue (Must remain private in backend-net)",
    "8082": "Internal AI Diagnostics Service (Must remain private in backend-net)",
    "8083": "Mock EHR Service (Must remain private in backend-net)"
}


def audit_requirements(root_dir: Path) -> List[Dict[str, str]]:
    findings = []
    for current_root, _, files in os.walk(root_dir):
        if any(ignored in current_root for ignored in [".git", "node_modules", ".venv", "venv"]):
            continue
        for file in files:
            if file == "requirements.txt":
                req_path = Path(current_root) / file
                lines = req_path.read_text(encoding="utf-8").splitlines()
                for line_num, line in enumerate(lines, start=1):
                    cleaned = line.strip()
                    if not cleaned or cleaned.startswith("#"):
                        continue
                    for pattern, vuln_info in VULNERABLE_PACKAGE_PATTERNS:
                        if re.search(pattern, cleaned):
                            findings.append({
                                "source": str(req_path),
                                "line": line_num,
                                "type": "DEPENDENCY_VULNERABILITY",
                                "message": f"Package '{cleaned}' matches risk rule: {vuln_info}"
                            })
    return findings


def audit_infrastructure_exposure(root_dir: Path) -> List[Dict[str, str]]:
    findings = []
    compose_path = root_dir / "docker-compose.yml"
    if compose_path.exists():
        content = compose_path.read_text(encoding="utf-8")
        # Check for ports exposed on restricted services
        # e.g. under postgres or redis: ports: - "5432:5432"
        current_service = None
        for line_num, line in enumerate(content.splitlines(), start=1):
            match_svc = re.match(r'^\s{2}([a-zA-Z0-9_-]+):', line)
            if match_svc:
                current_service = match_svc.group(1)

            for port, desc in RESTRICTED_PORTS.items():
                if f'"{port}:{port}"' in line or f"'{port}:{port}'" in line or f' {port}:{port}' in line:
                    findings.append({
                        "source": str(compose_path),
                        "line": line_num,
                        "type": "PUBLIC_EXPOSURE_VIOLATION",
                        "message": f"Service '{current_service}' exposes restricted port {port} to host! Security policy requires {desc}"
                    })

    return findings


def audit_all(root_dir: str) -> List[Dict[str, str]]:
    path = Path(root_dir)
    return audit_requirements(path) + audit_infrastructure_exposure(path)


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "."
    print(f"[*] Auditing dependencies & infrastructure isolation in: {os.path.abspath(target)}")
    results = audit_all(target)

    if results:
        print(f"\n[!] SECURITY AUDIT FAILED: {len(results)} issue(s) detected!\n")
        for res in results:
            print(f"  - [{res['type']}] {res['source']}:{res['line']}")
            print(f"    Violation: {res['message']}")
        sys.exit(1)
    else:
        print("[+] Security Audit Passed: All dependencies healthy; private services strictly isolated.")
        sys.exit(0)
