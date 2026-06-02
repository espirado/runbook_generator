from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from runbook_generator.cli import main


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
                    "production",
                    "--region",
                    "us-east-1",
                    "--cluster",
                    "payments-prod",
                    "--namespace",
                    "payments",
                    "--service",
                    "checkout-api",
                    "--output",
                    str(runbook_path),
                    "--snapshot-output",
                    str(snapshot_path),
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertIn("Operational Runbook", runbook_path.read_text())
            snapshot = json.loads(snapshot_path.read_text())
            self.assertEqual(snapshot["name"], "production")
            self.assertGreaterEqual(len(snapshot["resources"]), 1)


if __name__ == "__main__":
    unittest.main()
