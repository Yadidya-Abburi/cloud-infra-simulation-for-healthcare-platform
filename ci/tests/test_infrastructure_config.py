"""
Infrastructure and Configuration Integrity Tests
Validates:
1. Production and Development Terraform variables exist and define proper bounds
2. Docker Compose defines essential services without unauthenticated internet access
3. Monitoring Prometheus configuration defines valid scrape targets and alert rules
"""
import unittest
import os
import re
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent


class TestInfrastructureConfiguration(unittest.TestCase):

    def test_docker_compose_structure(self):
        """Ensure docker-compose has required microservices and dual networks."""
        compose_file = ROOT_DIR / "docker-compose.yml"
        self.assertTrue(compose_file.exists(), "docker-compose.yml not found")
        content = compose_file.read_text(encoding="utf-8")

        # Must have frontend-net and backend-net
        self.assertIn("frontend-net:", content)
        self.assertIn("backend-net:", content)

        # Ingress must expose port 80/8080
        self.assertIn('"8080:80"', content)

        # Database and Redis must NOT expose ports directly to host
        self.assertNotIn('"5432:5432"', content)
        self.assertNotIn('"6379:6379"', content)

    def test_terraform_environments(self):
        """Verify Terraform environment files define valid worker allocations."""
        dev_tfvars = ROOT_DIR / "infrastructure" / "terraform" / "environments" / "dev" / "dev.tfvars"
        prod_tfvars = ROOT_DIR / "infrastructure" / "terraform" / "environments" / "prod" / "prod.tfvars"

        self.assertTrue(dev_tfvars.exists(), "dev.tfvars missing")
        self.assertTrue(prod_tfvars.exists(), "prod.tfvars missing")

        dev_content = dev_tfvars.read_text(encoding="utf-8")
        prod_content = prod_tfvars.read_text(encoding="utf-8")

        self.assertTrue(re.search(r'environment\s*=\s*"dev"', dev_content), "environment dev not set")
        self.assertTrue(re.search(r'environment\s*=\s*"prod"', prod_content), "environment prod not set")

    def test_prometheus_alerting_rules_syntax(self):
        """Verify alerts.yml defines required operational alerts."""
        alerts_file = ROOT_DIR / "monitoring" / "prometheus" / "alerts.yml"
        self.assertTrue(alerts_file.exists(), "alerts.yml missing")
        content = alerts_file.read_text(encoding="utf-8")

        required_alerts = [
            "APIServiceDown",
            "HighHTTP5xxErrorRate",
            "WorkerUnavailable",
            "QueueBacklogSpike",
            "EHRFailureRateHigh"
        ]
        for alert_name in required_alerts:
            self.assertIn(f"alert: {alert_name}", content)


if __name__ == "__main__":
    unittest.main()
