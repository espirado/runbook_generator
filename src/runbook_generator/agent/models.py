"""Models for incident management and agent handoff artifacts."""

from __future__ import annotations

from dataclasses import dataclass, field

from runbook_generator.models import JsonDict, _utc_now_iso


@dataclass(slots=True)
class ObservabilitySignal:
    """A monitoring signal that should influence an incident or report."""

    source: str
    title: str
    severity: str = "info"
    status: str = "unknown"
    description: str | None = None
    query: str | None = None
    dashboard_url: str | None = None
    attributes: JsonDict = field(default_factory=dict)

    def to_dict(self) -> JsonDict:
        return {
            "source": self.source,
            "title": self.title,
            "severity": self.severity,
            "status": self.status,
            "description": self.description,
            "query": self.query,
            "dashboard_url": self.dashboard_url,
            "attributes": dict(self.attributes),
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> "ObservabilitySignal":
        return cls(
            source=str(data["source"]),
            title=str(data["title"]),
            severity=str(data.get("severity") or "info"),
            status=str(data.get("status") or "unknown"),
            description=data.get("description"),
            query=data.get("query"),
            dashboard_url=data.get("dashboard_url"),
            attributes=dict(data.get("attributes") or {}),
        )


@dataclass(slots=True)
class AgentInstruction:
    """A concrete task that an autonomous or human operator can execute."""

    title: str
    objective: str
    inputs: list[str] = field(default_factory=list)
    expected_output: str | None = None
    safety_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> JsonDict:
        return {
            "title": self.title,
            "objective": self.objective,
            "inputs": list(self.inputs),
            "expected_output": self.expected_output,
            "safety_notes": list(self.safety_notes),
        }


@dataclass(slots=True)
class IncidentReport:
    """Structured incident-management package derived from a runbook."""

    title: str
    environment: str
    service: str | None
    severity: str
    status: str = "draft"
    generated_at: str = field(default_factory=_utc_now_iso)
    summary: str = ""
    signals: list[ObservabilitySignal] = field(default_factory=list)
    suspected_impact: list[str] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)
    agent_instructions: list[AgentInstruction] = field(default_factory=list)
    runbook_path: str | None = None
    snapshot_path: str | None = None
    links: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> JsonDict:
        return {
            "title": self.title,
            "environment": self.environment,
            "service": self.service,
            "severity": self.severity,
            "status": self.status,
            "generated_at": self.generated_at,
            "summary": self.summary,
            "signals": [signal.to_dict() for signal in self.signals],
            "suspected_impact": list(self.suspected_impact),
            "recommended_actions": list(self.recommended_actions),
            "agent_instructions": [
                instruction.to_dict() for instruction in self.agent_instructions
            ],
            "runbook_path": self.runbook_path,
            "snapshot_path": self.snapshot_path,
            "links": dict(self.links),
        }
