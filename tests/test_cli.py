from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runbook_generator.cli import main


TEST_ENVIRONMENT = "test-environment"
TEST_REGION = "test-region-1"
TEST_CLUSTER = "test-cluster"
TEST_NAMESPACE = "test-namespace"
TEST_SERVICE = "test-service"


class CliTests(unittest.TestCase):
    def test_generate_fixture_writes_runbook_and_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            runbook_path = Path(tmpdir) / "runbook.md"
            snapshot_path = Path(tmpdir) / "snapshot.json"

            exit_code = main(
                [
                    "generate",
                    "--source",
                    "fixture",
                    "--environment",
                    TEST_ENVIRONMENT,
                    "--region",
                    TEST_REGION,
                    "--cluster",
                    TEST_CLUSTER,
                    "--namespace",
                    TEST_NAMESPACE,
                    "--service",
                    TEST_SERVICE,
                    "--output",
                    str(runbook_path),
                    "--snapshot-output",
                    str(snapshot_path),
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertIn("Operational Runbook", runbook_path.read_text())
            snapshot = json.loads(snapshot_path.read_text())
            self.assertEqual(snapshot["name"], TEST_ENVIRONMENT)
            self.assertGreaterEqual(len(snapshot["resources"]), 1)

    def test_generate_fixture_uses_environment_variable_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            runbook_path = Path(tmpdir) / "env-runbook.md"
            snapshot_path = Path(tmpdir) / "env-snapshot.json"
            env = {
                "RUNBOOK_SOURCE": "fixture",
                "RUNBOOK_ENVIRONMENT": "staging",
                "RUNBOOK_AWS_REGION": "us-west-2",
                "RUNBOOK_EKS_CLUSTER": "env-cluster",
                "RUNBOOK_K8S_NAMESPACE": "env-namespace",
                "RUNBOOK_SERVICE": "env-service",
                "RUNBOOK_OUTPUT": str(runbook_path),
                "RUNBOOK_SNAPSHOT_OUTPUT": str(snapshot_path),
            }

            with patch.dict("os.environ", env, clear=False):
                exit_code = main(["generate"])

            self.assertEqual(exit_code, 0)
            snapshot = json.loads(snapshot_path.read_text())
            self.assertEqual(snapshot["name"], "staging")
            self.assertEqual(snapshot["region"], "us-west-2")
            resource_names = {resource["name"] for resource in snapshot["resources"]}
            self.assertIn("env-service", resource_names)


if __name__ == "__main__":
    unittest.main()
