"""Platform-neutral data model for operational runbook generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


JsonDict = dict[str, Any]


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


@dataclass(slots=True)
class Resource:
    """A normalized operational resource discovered from any environment."""

    id: str
    name: str
    kind: str
    provider: str
    environment: str = "unknown"
    region: str | None = None
    status: str | None = None
    owner: str | None = None
    links: dict[str, str] = field(default_factory=dict)
    attributes: JsonDict = field(default_factory=dict)

    def to_dict(self) -> JsonDict:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "provider": self.provider,
            "environment": self.environment,
            "region": self.region,
            "status": self.status,
            "owner": self.owner,
            "links": dict(self.links),
            "attributes": dict(self.attributes),
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> "Resource":
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            kind=str(data["kind"]),
            provider=str(data["provider"]),
            environment=str(data.get("environment") or "unknown"),
            region=data.get("region"),
            status=data.get("status"),
            owner=data.get("owner"),
            links=dict(data.get("links") or {}),
            attributes=dict(data.get("attributes") or {}),
        )


@dataclass(slots=True)
class Relationship:
    """A directed dependency or operational relationship between resources."""

    source_id: str
    target_id: str
    relationship_type: str
    description: str | None = None

    def to_dict(self) -> JsonDict:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relationship_type": self.relationship_type,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> "Relationship":
        return cls(
            source_id=str(data["source_id"]),
            target_id=str(data["target_id"]),
            relationship_type=str(data["relationship_type"]),
            description=data.get("description"),
        )


@dataclass(slots=True)
class OperationalCheck:
    """A health, debugging, or recovery action surfaced in the runbook."""

    title: str
    command: str | None = None
    description: str | None = None
    severity: str = "info"

    def to_dict(self) -> JsonDict:
        return {
            "title": self.title,
            "command": self.command,
            "description": self.description,
            "severity": self.severity,
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> "OperationalCheck":
        return cls(
            title=str(data["title"]),
            command=data.get("command"),
            description=data.get("description"),
            severity=str(data.get("severity") or "info"),
        )


@dataclass(slots=True)
class EnvironmentSnapshot:
    """Normalized inventory used by renderers and future LLM synthesis."""

    name: str
    generated_at: str = field(default_factory=_utc_now_iso)
    providers: list[str] = field(default_factory=list)
    account: str | None = None
    region: str | None = None
    resources: list[Resource] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)
    checks: list[OperationalCheck] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: JsonDict = field(default_factory=dict)

    def add_resource(self, resource: Resource) -> None:
        if resource.id not in {existing.id for existing in self.resources}:
            self.resources.append(resource)

    def add_warning(self, warning: str) -> None:
        if warning not in self.warnings:
            self.warnings.append(warning)

    def to_dict(self) -> JsonDict:
        return {
            "name": self.name,
            "generated_at": self.generated_at,
            "providers": list(self.providers),
            "account": self.account,
            "region": self.region,
            "resources": [resource.to_dict() for resource in self.resources],
            "relationships": [
                relationship.to_dict() for relationship in self.relationships
            ],
            "checks": [check.to_dict() for check in self.checks],
            "warnings": list(self.warnings),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> "EnvironmentSnapshot":
        return cls(
            name=str(data["name"]),
            generated_at=str(data.get("generated_at") or _utc_now_iso()),
            providers=list(data.get("providers") or []),
            account=data.get("account"),
            region=data.get("region"),
            resources=[
                Resource.from_dict(resource)
                for resource in data.get("resources", [])
            ],
            relationships=[
                Relationship.from_dict(relationship)
                for relationship in data.get("relationships", [])
            ],
            checks=[
                OperationalCheck.from_dict(check)
                for check in data.get("checks", [])
            ],
            warnings=list(data.get("warnings") or []),
            metadata=dict(data.get("metadata") or {}),
        )
