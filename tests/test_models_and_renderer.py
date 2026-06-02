from __future__ import annotations

import unittest

from runbook_generator.collectors.base import CollectionTarget
from runbook_generator.collectors.fixture import FixtureCollector
from runbook_generator.models import EnvironmentSnapshot
from runbook_generator.render.markdown import MarkdownRunbookRenderer


class ModelAndRendererTests(unittest.TestCase):
    def test_snapshot_round_trip_preserves_resources(self) -> None:
        target = CollectionTarget(
            environment="production",
            region="us-east-1",
            cluster="payments-prod",
            namespace="payments",
            service="checkout-api",
        )
        snapshot = FixtureCollector().collect(target)

        restored = EnvironmentSnapshot.from_dict(snapshot.to_dict())

        self.assertEqual(restored.name, "production")
        self.assertEqual(restored.region, "us-east-1")
        self.assertEqual(len(restored.resources), len(snapshot.resources))
        self.assertEqual(len(restored.relationships), len(snapshot.relationships))

    def test_renderer_includes_operational_sections(self) -> None:
        snapshot = FixtureCollector().collect(
            CollectionTarget(
                environment="production",
                region="us-east-1",
                cluster="payments-prod",
                namespace="payments",
                service="checkout-api",
            )
        )

        markdown = MarkdownRunbookRenderer().render(snapshot)

        self.assertIn("# Operational Runbook: production", markdown)
        self.assertIn("## Resource inventory", markdown)
        self.assertIn("## Dependency and routing map", markdown)
        self.assertIn("## Health checks and debugging commands", markdown)
        self.assertIn("checkout-api", markdown)
        self.assertIn("aws.rds", markdown)


if __name__ == "__main__":
    unittest.main()
