"""
Unit and State Transition Tests for Blue-Green Deployment Controller
Validates:
1. Active color discovery from upstream configuration
2. Standby color determination
3. Upstream configuration file generation and atomic updates
4. Rollback state preservation
"""
import unittest
import tempfile
import sys
from pathlib import Path

# Add project root
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from deployment.scripts.switch_upstream import (
    get_standby_color,
    generate_upstream_content,
    switch_upstream_file,
    get_active_color
)
from deployment.scripts.deploy import BlueGreenDeployer


class TestDeploymentController(unittest.TestCase):

    def test_standby_color_alternation(self):
        """Ensure standby color alternates correctly between blue and green."""
        self.assertEqual(get_standby_color("blue"), "green")
        self.assertEqual(get_standby_color("green"), "blue")
        self.assertEqual(get_standby_color("BLUE"), "green")

    def test_generate_upstream_content(self):
        """Verify upstream.conf template format."""
        content_green = generate_upstream_content("green")
        self.assertIn("server api-green:8000", content_green)
        self.assertIn("upstream api_backend", content_green)

        content_blue = generate_upstream_content("blue")
        self.assertIn("server api-blue:8000", content_blue)

    def test_successful_simulation_rollout(self):
        """Verify full execution pipeline in simulation mode."""
        deployer = BlueGreenDeployer(
            target_version="v1.2.0",
            simulate_runtime=True,
            simulate_failure=False
        )
        initial_color = deployer.active_color
        success = deployer.execute()
        self.assertTrue(success, "Simulated rollout should succeed")

        # Active color should now be the new standby target
        active, _ = get_active_color()
        self.assertEqual(active, deployer.target_color)

    def test_failed_simulation_triggers_rollback(self):
        """Verify simulated readiness failure halts rollout and restores initial state."""
        # First ensure active is blue
        switch_upstream_file("blue")
        deployer = BlueGreenDeployer(
            target_version="v2.0.0-broken",
            simulate_runtime=True,
            simulate_failure=True
        )
        success = deployer.execute()
        self.assertFalse(success, "Deployment with simulated failure must return False")

        # Rollback must restore upstream to blue
        active, _ = get_active_color()
        self.assertEqual(active, "blue", "Rollback failed to restore active color to blue")


if __name__ == "__main__":
    unittest.main()
