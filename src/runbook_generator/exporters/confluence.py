"""Confluence page payload renderer."""

from __future__ import annotations

from dataclasses import dataclass

from runbook_generator.agent.models import IncidentReport
from runbook_generator.models import JsonDict


@dataclass(frozen=True, slots=True)
class ConfluenceTarget:
    """Confluence destination metadata for a generated runbook page."""

    base_url: str | None
    space_key: str | None
    parent_page_id: str | None


class ConfluenceExporter:
    """Render a Confluence create-page payload without posting it."""

    def __init__(self, target: ConfluenceTarget) -> None:
        self.target = target

    def render_payload(self, report: IncidentReport, runbook_markdown: str) -> JsonDict:
        body = self._storage_body(report, runbook_markdown)
        payload: JsonDict = {
            "type": "page",
            "title": report.title,
            "body": {
                "storage": {
                    "value": body,
                    "representation": "storage",
                }
            },
        }
        if self.target.space_key:
            payload["space"] = {"key": self.target.space_key}
        if self.target.parent_page_id:
            payload["ancestors"] = [{"id": self.target.parent_page_id}]

        return {
            "destination": {
                "type": "confluence",
                "base_url": self.target.base_url,
                "space_key": self.target.space_key,
                "parent_page_id": self.target.parent_page_id,
            },
            "method": "POST",
            "path": "/rest/api/content",
            "payload": payload,
            "publish_state": "dry_run",
        }

    @staticmethod
    def _storage_body(report: IncidentReport, runbook_markdown: str) -> str:
        escaped_runbook = (
            runbook_markdown.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        return (
            f"<h1>{report.title}</h1>"
            f"<p><strong>Environment:</strong> {report.environment}</p>"
            f"<p><strong>Severity:</strong> {report.severity}</p>"
            "<h2>Generated runbook</h2>"
            f"<ac:structured-macro ac:name=\"code\">"
            f"<ac:plain-text-body><![CDATA[{escaped_runbook}]]></ac:plain-text-body>"
            f"</ac:structured-macro>"
        )
