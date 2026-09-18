"""
Test Security Rules and Validation Gates
Verifies that the automated security scanners deterministically detect:
1. Hardcoded API keys and tokens
2. Dockerfile root execution vulnerabilities
3. Exposed private ports in infrastructure configs
"""
import unittest
import tempfile
import sys
from pathlib import Path

# Add ci directory to sys.path
CI_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CI_DIR))

from security.secret_scanner import scan_file
from security.dockerfile_linter import lint_dockerfile, SEVERITY_HIGH
from security.dependency_auditor import audit_infrastructure_exposure, audit_requirements


class TestSecurityValidationGates(unittest.TestCase):

    def test_secret_scanner_detects_api_key(self):
        """Ensure secret scanner catches raw API keys in files."""
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".py", delete=False) as f:
            f.write('OPENAI_API_KEY = "sk-live-1234567890abcdef1234567890"\n')
            temp_path = Path(f.name)

        try:
            findings = scan_file(temp_path)
            self.assertGreater(len(findings), 0, "Secret scanner failed to catch live API key pattern")
            self.assertEqual(findings[0]["description"], "Potential Hardcoded API/Secret Key")
        finally:
            temp_path.unlink()

    def test_secret_scanner_detects_private_key(self):
        """Ensure secret scanner flags exposed RSA private keys."""
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".key", delete=False) as f:
            f.write("-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0\n-----END RSA PRIVATE KEY-----\n")
            temp_path = Path(f.name)

        try:
            findings = scan_file(temp_path)
            self.assertGreater(len(findings), 0, "Secret scanner failed to catch private key block")
            self.assertEqual(findings[0]["description"], "Exposed Private Cryptographic Key")
        finally:
            temp_path.unlink()

    def test_dockerfile_linter_detects_missing_user(self):
        """Ensure dockerfile linter catches omission of USER directive."""
        with tempfile.NamedTemporaryFile(mode="w+", suffix="Dockerfile", delete=False) as f:
            f.write("FROM python:3.11-slim\nWORKDIR /app\nCOPY . .\nCMD [\"python\", \"main.py\"]\n")
            temp_path = Path(f.name)

        try:
            issues = lint_dockerfile(temp_path)
            high_severity = [i for i in issues if i["severity"] == SEVERITY_HIGH]
            self.assertGreater(len(high_severity), 0, "Linter missed missing USER instruction")
            self.assertIn("non-root USER", high_severity[0]["message"])
        finally:
            temp_path.unlink()

    def test_dockerfile_linter_detects_root_switch(self):
        """Ensure dockerfile linter catches explicit USER root."""
        with tempfile.NamedTemporaryFile(mode="w+", suffix="Dockerfile", delete=False) as f:
            f.write("FROM python:3.11-slim\nUSER root\nCMD [\"python\", \"main.py\"]\n")
            temp_path = Path(f.name)

        try:
            issues = lint_dockerfile(temp_path)
            high_severity = [i for i in issues if i["severity"] == SEVERITY_HIGH]
            self.assertGreater(len(high_severity), 0, "Linter missed explicit switch to root")
            self.assertIn("'root' or '0'", high_severity[0]["message"])
        finally:
            temp_path.unlink()

    def test_exposure_auditor_detects_exposed_postgres(self):
        """Ensure infrastructure auditor catches postgres port exposed to host."""
        with tempfile.TemporaryDirectory() as tmpdir:
            compose_file = Path(tmpdir) / "docker-compose.yml"
            compose_file.write_text(
                "services:\n"
                "  postgres:\n"
                "    image: postgres:16-alpine\n"
                "    ports:\n"
                "      - \"5432:5432\"\n"
            )
            findings = audit_infrastructure_exposure(Path(tmpdir))
            self.assertGreater(len(findings), 0, "Auditor failed to catch exposed database port 5432")
            self.assertIn("5432", findings[0]["message"])


if __name__ == "__main__":
    unittest.main()
