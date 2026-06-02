"""Jira incident payload renderer."""

from __future__ import annotations

from dataclasses import dataclass

from runbook_generator.agent.models import IncidentReport
from runbook_generator.models import JsonDict


@dataclass(frozen=True, slots=True)
class JiraTarget:
    """Jira destination metadata for a generated incident payload."""

    base_url: str | None
    project_key: str | None
    issue_type: str


class JiraExporter:
    """Render a Jira create-issue payload without posting it."""

    def __init__(self, target: JiraTarget) -> None:
        self.target = target

    def render_payload(self, report: IncidentReport) -> JsonDict:
        description = [
            report.summary,
            "",
            "Recommended actions:",
            *[f"- {action}" for action in report.recommended_actions],
            "",
            "Observability signals:",
            *[
                f"- {signal.title} [{signal.status}/{signal.severity}]"
                for signal in report.signals
            ],
        ]
        fields: JsonDict = {
            "summary": report.title,
            "description": "\n".join(description).rstrip(),
            "issuetype": {"name": self.target.issue_type},
            "labels": [
                "runbook-generator",
                "incident-management",
                f"environment-{report.environment}",
            ],
        }
        if self.target.project_key:
            fields["project"] = {"key": self.target.project_key}

        return {
            "destination": {
                "type": "jira",
                "base_url": self.target.base_url,
                "project_key": self.target.project_key,
                "issue_type": self.target.issue_type,
            },
            "method": "POST",
            "path": "/rest/api/2/issue",
            "payload": {"fields": fields},
            "publish_state": "dry_run",
        }
