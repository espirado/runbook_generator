"""Observability integrations used by incident/report generation."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from runbook_generator.agent.models import ObservabilitySignal


@dataclass(frozen=True, slots=True)
class ObservabilityConfig:
    """Configuration for a monitoring platform query."""

    provider: str | None
    base_url: str | None
    query: str | None
    dashboard_url: str | None


class ObservabilityClient:
    """Best-effort observability client with safe offline fallbacks."""

    def collect_signals(self, config: ObservabilityConfig) -> list[ObservabilitySignal]:
        if not config.provider:
            return [
                ObservabilitySignal(
                    source="observability",
                    title="No observability provider configured",
                    severity="info",
                    status="not_configured",
                    description=(
                        "Set RUNBOOK_OBSERVABILITY_PROVIDER and related variables "
                        "to include live monitoring context."
                    ),
                )
            ]

        provider = config.provider.lower()
        if provider == "prometheus":
            return self._collect_prometheus(config)

        return [
            ObservabilitySignal(
                source=config.provider,
                title="Observability context configured",
                severity="info",
                status="configured",
                description=(
                    "Provider-specific live query support is not implemented yet; "
                    "the report includes configured platform metadata."
                ),
                query=config.query,
                dashboard_url=config.dashboard_url,
            )
        ]

    def _collect_prometheus(
        self,
        config: ObservabilityConfig,
    ) -> list[ObservabilitySignal]:
        if not config.base_url or not config.query:
            return [
                ObservabilitySignal(
                    source="prometheus",
                    title="Prometheus query not configured",
                    severity="warning",
                    status="missing_query",
                    description=(
                        "Set RUNBOOK_OBSERVABILITY_BASE_URL and "
                        "RUNBOOK_OBSERVABILITY_QUERY to query Prometheus."
                    ),
                    dashboard_url=config.dashboard_url,
                )
            ]

        url = self._prometheus_query_url(config.base_url, config.query)
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # pragma: no cover - network failures vary.
            return [
                ObservabilitySignal(
                    source="prometheus",
                    title="Prometheus query failed",
                    severity="warning",
                    status="query_failed",
                    description=str(exc),
                    query=config.query,
                    dashboard_url=config.dashboard_url,
                    attributes={"url": url},
                )
            ]

        result = payload.get("data", {}).get("result", [])
        if not result:
            return [
                ObservabilitySignal(
                    source="prometheus",
                    title="Prometheus query returned no active series",
                    severity="info",
                    status="ok",
                    query=config.query,
                    dashboard_url=config.dashboard_url,
                    attributes={"url": url},
                )
            ]

        return [
            ObservabilitySignal(
                source="prometheus",
                title="Prometheus query returned active series",
                severity="warning",
                status="active",
                description=f"{len(result)} time series matched the configured query.",
                query=config.query,
                dashboard_url=config.dashboard_url,
                attributes={
                    "url": url,
                    "sample": self._sample_result(result),
                    "series_count": len(result),
                },
            )
        ]

    @staticmethod
    def _prometheus_query_url(base_url: str, query: str) -> str:
        base = base_url.rstrip("/")
        encoded = urllib.parse.urlencode({"query": query})
        return f"{base}/api/v1/query?{encoded}"

    @staticmethod
    def _sample_result(result: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return result[:3]
