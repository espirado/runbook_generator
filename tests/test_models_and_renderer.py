from __future__ import annotations

import unittest

from runbook_generator.collectors.base import CollectionTarget
from runbook_generator.collectors.fixture import FixtureCollector
from runbook_generator.models import EnvironmentSnapshot
from runbook_generator.render.markdown import MarkdownRunbookRenderer


TEST_ENVIRONMENT = "test-environment"
TEST_REGION = "test-region-1"
TEST_CLUSTER = "test-cluster"
TEST_NAMESPACE = "test-namespace"
TEST_SERVICE = "test-service"


class ModelAndRendererTests(unittest.TestCase):
    def test_snapshot_round_trip_preserves_resources(self) -> None:
        target = CollectionTarget(
            environment=TEST_ENVIRONMENT,
            region=TEST_REGION,
            cluster=TEST_CLUSTER,
            namespace=TEST_NAMESPACE,
            service=TEST_SERVICE,
        )
        snapshot = FixtureCollector().collect(target)

        restored = EnvironmentSnapshot.from_dict(snapshot.to_dict())

        self.assertEqual(restored.name, TEST_ENVIRONMENT)
        self.assertEqual(restored.region, TEST_REGION)
        self.assertEqual(len(restored.resources), len(snapshot.resources))
        self.assertEqual(len(restored.relationships), len(snapshot.relationships))

    def test_renderer_includes_operational_sections(self) -> None:
        snapshot = FixtureCollector().collect(
            CollectionTarget(
                environment=TEST_ENVIRONMENT,
                region=TEST_REGION,
                cluster=TEST_CLUSTER,
                namespace=TEST_NAMESPACE,
                service=TEST_SERVICE,
            )
        )

        markdown = MarkdownRunbookRenderer().render(snapshot)

        self.assertIn(f"# Operational Runbook: {TEST_ENVIRONMENT}", markdown)
        self.assertIn("## Resource inventory", markdown)
        self.assertIn("## Dependency and routing map", markdown)
        self.assertIn("## Health checks and debugging commands", markdown)
        self.assertIn(TEST_SERVICE, markdown)
        self.assertIn("aws.rds", markdown)


if __name__ == "__main__":
    unittest.main()
