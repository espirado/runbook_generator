"""Shared collector protocol and target definition."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from runbook_generator.models import EnvironmentSnapshot


@dataclass(frozen=True, slots=True)
class CollectionTarget:
    """User-selected scope for a runbook generation request."""

    environment: str
    account: str | None = None
    region: str | None = None
    cluster: str | None = None
    namespace: str | None = None
    service: str | None = None
    kube_context: str | None = None


class Collector(Protocol):
    """A platform-specific inventory collector."""

    name: str

    def collect(self, target: CollectionTarget) -> EnvironmentSnapshot:
        """Collect live or fixture data into a normalized snapshot."""
