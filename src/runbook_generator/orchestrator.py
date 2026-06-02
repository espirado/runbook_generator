"""Pipeline orchestration for collecting snapshots and rendering runbooks."""

from __future__ import annotations

from collections.abc import Iterable

from runbook_generator.collectors.base import CollectionTarget, Collector
from runbook_generator.models import EnvironmentSnapshot
from runbook_generator.render.markdown import MarkdownRunbookRenderer


class RunbookGenerator:
    """Collect environment state and render an operational runbook."""

    def __init__(
        self,
        collectors: Iterable[Collector],
        renderer: MarkdownRunbookRenderer | None = None,
    ) -> None:
        self.collectors = list(collectors)
        self.renderer = renderer or MarkdownRunbookRenderer()

    def collect(self, target: CollectionTarget) -> EnvironmentSnapshot:
        merged = EnvironmentSnapshot(
            name=target.environment,
            account=target.account,
            region=target.region,
            metadata={"target": self._target_metadata(target)},
        )

        for collector in self.collectors:
            snapshot = collector.collect(target)
            self._merge(merged, snapshot)

        if not merged.resources:
            merged.add_warning(
                "No resources were discovered. Check credentials, region, namespace, and collector configuration."
            )

        return merged

    def generate(self, target: CollectionTarget) -> tuple[EnvironmentSnapshot, str]:
        snapshot = self.collect(target)
        return snapshot, self.renderer.render(snapshot)

    @staticmethod
    def _merge(
        destination: EnvironmentSnapshot,
        source: EnvironmentSnapshot,
    ) -> None:
        destination.account = destination.account or source.account
        destination.region = destination.region or source.region
        for provider in source.providers:
            if provider not in destination.providers:
                destination.providers.append(provider)
        for resource in source.resources:
            destination.add_resource(resource)
        destination.relationships.extend(source.relationships)
        destination.checks.extend(source.checks)
        for warning in source.warnings:
            destination.add_warning(warning)
        destination.metadata.update(source.metadata)

    @staticmethod
    def _target_metadata(target: CollectionTarget) -> dict[str, str | None]:
        return {
            "environment": target.environment,
            "account": target.account,
            "region": target.region,
            "cluster": target.cluster,
            "namespace": target.namespace,
            "service": target.service,
            "kube_context": target.kube_context,
        }
