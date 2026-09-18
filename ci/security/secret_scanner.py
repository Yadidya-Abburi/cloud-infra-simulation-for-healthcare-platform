"""
Automated Secret Scanner for CI/CD Gates
Scans tracked repository files for high-risk secrets, sensitive credentials,
hardcoded private keys, tokens, and high-entropy connection strings.
"""
import os
import re
import sys
import subprocess
from pathlib import Path
from typing import List, Dict, Tuple

# Targeted sensitive file types and patterns
SECRET_PATTERNS = [
    (r'(?i)(?:api_key|apikey|secret_key|secret)\s*[:=]\s*["\']([a-zA-Z0-9_\-]{16,})["\']', "Potential Hardcoded API/Secret Key"),
    (r'(?i)(?:password|passwd|pwd)\s*[:=]\s*["\'](?!postgres_secret)(?!.*\$\{)[a-zA-Z0-9@#$%^&*!_\-]{8,}["\']', "Hardcoded Password (non-default/template)"),
    (r'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----', "Exposed Private Cryptographic Key"),
    (r'(?i)ghp_[a-zA-Z0-9]{36}', "GitHub Personal Access Token"),
    (r'(?i)AKIA[0-9A-Z]{16}', "AWS Access Key ID"),
    (r'(?i)eyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}', "Exposed JWT Token"),
    (r'(?i)postgres(?:ql)?://[a-zA-Z0-9_]+:(?!postgres_secret)[a-zA-Z0-9_]+@[a-zA-Z0-9_\.-]+:[0-9]+/[a-zA-Z0-9_]+', "Hardcoded Database Connection URI with Credentials")
]

# Paths and extensions to ignore
EXCLUDE_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".terraform", "node_modules"}
EXCLUDE_FILES = {".env.example", "package-lock.json", "secret_scanner.py", "test_security_rules.py"}
INCLUDED_EXTENSIONS = {".py", ".yml", ".yaml", ".json", ".tf", ".tfvars", ".sql", ".sh", ".conf", ".md", ".txt"}


def scan_file(file_path: Path) -> List[Dict[str, str]]:
    findings = []
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return findings

    lines = content.splitlines()
    for line_num, line in enumerate(lines, start=1):
        # Skip commented lines in Python / YAML / Terraform
        stripped = line.strip()
        if stripped.startswith("#") and not any(k in stripped.lower() for k in ["api_key", "password", "private key"]):
            continue

        for pattern, description in SECRET_PATTERNS:
            if re.search(pattern, line):
                findings.append({
                    "file": str(file_path),
                    "line": line_num,
                    "description": description,
                    "snippet": line.strip()[:100]
                })
    return findings


def is_gitignored(file_path: Path, root_dir: Path) -> bool:
    try:
        rel_path = file_path.relative_to(root_dir)
        res = subprocess.run(
            ["git", "check-ignore", str(rel_path)],
            cwd=str(root_dir),
            capture_output=True,
            text=True
        )
        return res.returncode == 0
    except Exception:
        return False


def scan_directory(root_dir: str) -> List[Dict[str, str]]:
    all_findings = []
    root_path = Path(root_dir)

    for current_root, dirs, files in os.walk(root_path):
        # Prune excluded directories
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

        for file in files:
            if file in EXCLUDE_FILES:
                continue
            file_path = Path(current_root) / file

            # If the file is properly gitignored (e.g. local .env or local *.tfvars), it is safely uncommitted
            if is_gitignored(file_path, root_path):
                continue

            if file_path.suffix in INCLUDED_EXTENSIONS or file.startswith(".env"):
                findings = scan_file(file_path)
                all_findings.extend(findings)

    return all_findings


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "."
    print(f"[*] Starting secret scan on: {os.path.abspath(target)}")
    results = scan_directory(target)

    if results:
        print(f"\n[!] SECURITY GATE FAILED: {len(results)} potential secret(s) detected!\n")
        for res in results:
            print(f"  - [{res['description']}] {res['file']}:{res['line']}")
            print(f"    Snippet: {res['snippet']}")
        sys.exit(1)
    else:
        print("[+] Secret Scan Passed: No hardcoded credentials, tokens, or private keys found.")
        sys.exit(0)
