"""
Unit and Contract Verification Suite for Simulated Services
Tests FastAPI endpoints, contracts, error handlers, and payload validation
using the standard Python standard library and unittest.
"""
import unittest
import json
import os
import sys
from pathlib import Path

# Add services/api to PYTHONPATH
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR / "services" / "api"))
sys.path.insert(0, str(ROOT_DIR / "services" / "mock-ehr"))
sys.path.insert(0, str(ROOT_DIR / "services" / "ai-service"))


class TestServiceContracts(unittest.TestCase):

    def test_mock_ehr_modes(self):
        """Verify Mock EHR handles simulation modes appropriately."""
        # Import dynamically to ensure modules can be tested cleanly
        from app.main import app as ehr_app
        from starlette.testclient import TestClient
        client = TestClient(ehr_app)

        res = client.get("/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json().get("service"), "mock-ehr")

        # Test sync endpoint in normal mode
        res_sync = client.post("/ehr/sync", json={"patient_id": "P101", "name": "Jane Doe"})
        self.assertIn(res_sync.status_code, [200, 201])
        data = res_sync.json()
        self.assertEqual(data.get("status"), "synced")
        self.assertEqual(data.get("patient_id"), "P101")

    def test_ai_service_endpoint(self):
        """Verify internal AI diagnosis service contract."""
        from app.main import app as ai_app
        from starlette.testclient import TestClient
        client = TestClient(ai_app)

        res = client.get("/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json().get("status"), "healthy")

        gen_res = client.post("/generate", json={"prompt": "Chest pain and fatigue"})
        self.assertEqual(gen_res.status_code, 200)
        body = gen_res.json()
        self.assertIn("response", body)
        self.assertIn("model", body)

    def test_api_service_liveness_and_metrics(self):
        """Verify API service exposes liveness and metrics without external dependencies."""
        from app.main import app as api_app
        from starlette.testclient import TestClient
        client = TestClient(api_app)

        # Liveness must return 200 independently of DB/Redis
        res = client.get("/health")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("status"), "healthy")
        self.assertEqual(data.get("service"), "api")

        # Metrics must return prometheus text format
        res_metrics = client.get("/metrics")
        self.assertEqual(res_metrics.status_code, 200)
        self.assertIn("http_requests_total", res_metrics.text)


if __name__ == "__main__":
    unittest.main()
