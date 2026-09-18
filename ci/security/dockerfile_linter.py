"""
Dockerfile & Container Hardening Security Linter
Validates Dockerfiles against DevSecOps and container security best practices:
1. Enforces non-root execution (USER directive required)
2. Flags usage of ':latest' or untagged base images
3. Ensures clean package manager invocations (avoid cached package layers)
4. Checks that sensitive files are not copied into container layers
"""
import os
import re
import sys
from pathlib import Path
from typing import List, Dict

SEVERITY_HIGH = "HIGH"
SEVERITY_MEDIUM = "MEDIUM"
SEVERITY_LOW = "LOW"


def lint_dockerfile(file_path: Path) -> List[Dict[str, str]]:
    issues = []
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        return [{"file": str(file_path), "line": 0, "severity": SEVERITY_HIGH, "message": f"Could not read Dockerfile: {e}"}]

    lines = content.splitlines()
    has_user_directive = False
    has_from_directive = False

    for line_num, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        # Check FROM instruction
        if line.upper().startswith("FROM "):
            has_from_directive = True
            image_part = line.split()[1]
            if ":" not in image_part or image_part.endswith(":latest"):
                issues.append({
                    "file": str(file_path),
                    "line": line_num,
                    "severity": SEVERITY_MEDIUM,
                    "message": f"Base image '{image_part}' uses implicit or explicit ':latest' tag. Pin to immutable version."
                })

        # Check USER instruction
        if line.upper().startswith("USER "):
            has_user_directive = True
            user_val = line.split()[1]
            if user_val in ["root", "0"]:
                issues.append({
                    "file": str(file_path),
                    "line": line_num,
                    "severity": SEVERITY_HIGH,
                    "message": "Explicitly switches back to 'root' or '0' user."
                })

        # Check for dangerous COPY of sensitive files
        if re.search(r'(?i)COPY\s+.*(?:\.env|id_rsa|\.pem|credentials)', line):
            issues.append({
                "file": str(file_path),
                "line": line_num,
                "severity": SEVERITY_HIGH,
                "message": f"Detected copying of potentially sensitive files: '{line}'"
            })

        # Check apt-get / apk cache cleanup
        if "apt-get install" in line and "rm -rf /var/lib/apt/lists/*" not in content:
            issues.append({
                "file": str(file_path),
                "line": line_num,
                "severity": SEVERITY_LOW,
                "message": "apt-get install does not clean up /var/lib/apt/lists/*, inflating image attack surface."
            })

    if has_from_directive and not has_user_directive:
        issues.append({
            "file": str(file_path),
            "line": 1,
            "severity": SEVERITY_HIGH,
            "message": "Dockerfile does not declare a non-root USER instruction. Container will run as root by default."
        })

    return issues


def lint_all_dockerfiles(root_dir: str) -> List[Dict[str, str]]:
    all_issues = []
    root_path = Path(root_dir)

    for current_root, _, files in os.walk(root_path):
        if any(ignored in current_root for ignored in [".git", "node_modules", ".terraform"]):
            continue
        for file in files:
            if file == "Dockerfile" or file.endswith(".Dockerfile"):
                file_path = Path(current_root) / file
                issues = lint_dockerfile(file_path)
                all_issues.extend(issues)

    return all_issues


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "."
    print(f"[*] Linting Dockerfiles in: {os.path.abspath(target)}")
    results = lint_all_dockerfiles(target)

    high_issues = [r for r in results if r["severity"] == SEVERITY_HIGH]

    if high_issues:
        print(f"\n[!] CONTAINER SECURITY GATE FAILED: {len(high_issues)} HIGH severity finding(s) detected!\n")
        for res in results:
            print(f"  - [{res['severity']}] {res['file']}:{res['line']} -> {res['message']}")
        sys.exit(1)
    elif results:
        print(f"\n[?] Passed with {len(results)} non-blocking warnings:")
        for res in results:
            print(f"  - [{res['severity']}] {res['file']}:{res['line']} -> {res['message']}")
        sys.exit(0)
    else:
        print("[+] Container Security Gate Passed: All Dockerfiles enforce non-root execution and security best practices.")
        sys.exit(0)
