"""Build agent, incident-management, and reporting artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from runbook_generator.agent.models import (
    AgentInstruction,
    IncidentReport,
    ObservabilitySignal,
)
from runbook_generator.agent.observability import (
    ObservabilityClient,
    ObservabilityConfig,
)
from runbook_generator.exporters.confluence import ConfluenceExporter, ConfluenceTarget
from runbook_generator.exporters.jira import JiraExporter, JiraTarget
from runbook_generator.exporters.wiki import WikiExporter, WikiTarget
from runbook_generator.models import EnvironmentSnapshot


class AgentOpsWorkflow:
    """Create a portable ops package from a runbook and environment snapshot."""

    def __init__(
        self,
        observability_client: ObservabilityClient | None = None,
    ) -> None:
        self.observability_client = observability_client or ObservabilityClient()

    def create_package(
        self,
        snapshot: EnvironmentSnapshot,
        runbook: str,
        output_dir: Path,
        observability_config: ObservabilityConfig,
        confluence_target: ConfluenceTarget,
        jira_target: JiraTarget,
        wiki_target: WikiTarget,
        runbook_path: str | None = None,
        snapshot_path: str | None = None,
    ) -> dict[str, str]:
        output_dir.mkdir(parents=True, exist_ok=True)
        signals = self.observability_client.collect_signals(observability_config)
        report = self.build_incident_report(
            snapshot=snapshot,
            signals=signals,
            runbook_path=runbook_path,
            snapshot_path=snapshot_path,
        )

        artifacts: dict[str, str] = {}
        artifacts["runbook"] = self._write(
            output_dir / "runbook.md",
            runbook,
        )
        artifacts["snapshot"] = self._write(
            output_dir / "snapshot.json",
            json.dumps(snapshot.to_dict(), indent=2, sort_keys=True) + "\n",
        )
        artifacts["observability_signals"] = self._write(
            output_dir / "observability_signals.json",
            json.dumps([signal.to_dict() for signal in signals], indent=2, sort_keys=True)
            + "\n",
        )
        artifacts["incident_report"] = self._write(
            output_dir / "incident_report.md",
            self.render_incident_report(report),
        )
        artifacts["jira_payload"] = self._write(
            output_dir / "jira_issue.json",
            json.dumps(
                JiraExporter(jira_target).render_payload(report),
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )
        artifacts["confluence_payload"] = self._write(
            output_dir / "confluence_page.json",
            json.dumps(
                ConfluenceExporter(confluence_target).render_payload(report, runbook),
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )
        artifacts["wiki_page"] = self._write(
            output_dir / "wiki_page.md",
            WikiExporter(wiki_target).render_page(report, runbook),
        )
        artifacts["agent_context"] = self._write(
            output_dir / "agent_context.json",
            json.dumps(self.agent_context(report, artifacts), indent=2, sort_keys=True)
            + "\n",
        )
        return artifacts

    def build_incident_report(
        self,
        snapshot: EnvironmentSnapshot,
        signals: list[ObservabilitySignal],
        runbook_path: str | None,
        snapshot_path: str | None,
    ) -> IncidentReport:
        service = self._primary_service(snapshot)
        severity = self._highest_severity(signals)
        title_subject = service or snapshot.name
        report = IncidentReport(
            title=f"Operational report for {title_subject}",
            environment=snapshot.name,
            service=service,
            severity=severity,
            summary=(
                f"Generated from {len(snapshot.resources)} discovered resources, "
                f"{len(snapshot.relationships)} relationships, and "
                f"{len(signals)} observability signals."
            ),
            signals=signals,
            suspected_impact=self._suspected_impact(snapshot, signals),
            recommended_actions=self._recommended_actions(snapshot),
            agent_instructions=self._agent_instructions(),
            runbook_path=runbook_path,
            snapshot_path=snapshot_path,
        )
        return report

    def render_incident_report(self, report: IncidentReport) -> str:
        lines = [
            f"# {report.title}",
            "",
            f"- Environment: `{report.environment}`",
            f"- Service: `{report.service or 'unknown'}`",
            f"- Severity: `{report.severity}`",
            f"- Status: `{report.status}`",
            f"- Generated at: `{report.generated_at}`",
            "",
            "## Summary",
            "",
            report.summary,
            "",
            "## Observability signals",
            "",
        ]
        for signal in report.signals:
            lines.append(
                f"- **{signal.title}** `{signal.status}` `{signal.severity}`"
                + (f" - {signal.description}" if signal.description else "")
            )
            if signal.dashboard_url:
                lines.append(f"  - Dashboard: {signal.dashboard_url}")
            if signal.query:
                lines.append(f"  - Query: `{signal.query}`")
        lines.extend(["", "## Suspected impact", ""])
        lines.extend([f"- {impact}" for impact in report.suspected_impact])
        lines.extend(["", "## Recommended actions", ""])
        lines.extend([f"{index}. {action}" for index, action in enumerate(report.recommended_actions, 1)])
        lines.extend(["", "## Agent instructions", ""])
        for instruction in report.agent_instructions:
            lines.extend(
                [
                    f"### {instruction.title}",
                    "",
                    instruction.objective,
                    "",
                    "**Inputs**",
                    "",
                ]
            )
            lines.extend([f"- {item}" for item in instruction.inputs])
            if instruction.expected_output:
                lines.extend(["", f"Expected output: {instruction.expected_output}"])
            if instruction.safety_notes:
                lines.extend(["", "**Safety notes**", ""])
                lines.extend([f"- {note}" for note in instruction.safety_notes])
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def agent_context(
        self,
        report: IncidentReport,
        artifacts: dict[str, str],
    ) -> dict[str, object]:
        return {
            "schema": "runbook-generator.agent-context.v1",
            "title": report.title,
            "environment": report.environment,
            "service": report.service,
            "severity": report.severity,
            "status": report.status,
            "artifacts": dict(artifacts),
            "instructions": [
                instruction.to_dict() for instruction in report.agent_instructions
            ],
            "recommended_actions": list(report.recommended_actions),
            "signals": [signal.to_dict() for signal in report.signals],
        }

    @staticmethod
    def _write(path: Path, content: str) -> str:
        path.write_text(content, encoding="utf-8")
        return str(path)

    @staticmethod
    def _primary_service(snapshot: EnvironmentSnapshot) -> str | None:
        for resource in snapshot.resources:
            if resource.kind in {"compute.workload", "compute.serverless_function"}:
                return resource.name
        return None

    @staticmethod
    def _highest_severity(signals: list[ObservabilitySignal]) -> str:
        order = {"critical": 4, "error": 3, "warning": 2, "info": 1}
        return max(
            (signal.severity for signal in signals),
            key=lambda item: order.get(item, 0),
            default="info",
        )

    @staticmethod
    def _suspected_impact(
        snapshot: EnvironmentSnapshot,
        signals: list[ObservabilitySignal],
    ) -> list[str]:
        impact = []
        if any(signal.status in {"active", "query_failed"} for signal in signals):
            impact.append("Monitoring signals require operator review.")
        if any(resource.kind == "network.load_balancer" for resource in snapshot.resources):
            impact.append("Traffic serving path may be affected.")
        if any(resource.kind == "data.database" for resource in snapshot.resources):
            impact.append("Data dependency health should be verified before recovery actions.")
        if not impact:
            impact.append("No active customer impact inferred from available signals.")
        return impact

    @staticmethod
    def _recommended_actions(snapshot: EnvironmentSnapshot) -> list[str]:
        actions = [
            "Open the generated runbook and confirm environment/account/cluster context.",
            "Review observability signals and active alerts before taking action.",
            "Check recent deploys, workload health, and dependency health.",
        ]
        if snapshot.checks:
            actions.append("Run the health/debugging commands included in the runbook.")
        actions.extend(
            [
                "Create or update the incident ticket with findings and mitigation steps.",
                "Publish the runbook/wiki page once validated by the owning team.",
            ]
        )
        return actions

    @staticmethod
    def _agent_instructions() -> list[AgentInstruction]:
        return [
            AgentInstruction(
                title="Triage live system state",
                objective=(
                    "Use the snapshot, runbook, and observability signals to identify "
                    "the failing layer without making destructive changes."
                ),
                inputs=[
                    "snapshot.json",
                    "runbook.md",
                    "observability_signals.json",
                ],
                expected_output="A concise triage summary with suspected cause and evidence.",
                safety_notes=[
                    "Do not restart, scale, rollback, or change cloud resources without explicit approval.",
                    "Verify account, region, namespace, and cluster before running commands.",
                ],
            ),
            AgentInstruction(
                title="Prepare incident communications",
                objective=(
                    "Use the incident report and Jira payload to draft operator-facing "
                    "updates and next actions."
                ),
                inputs=["incident_report.md", "jira_issue.json"],
                expected_output="A ready-to-review incident update and ticket description.",
                safety_notes=[
                    "Do not claim customer impact unless supported by observability data.",
                    "Mark unknown owners or missing dashboards as gaps.",
                ],
            ),
            AgentInstruction(
                title="Publish validated knowledge",
                objective=(
                    "After human validation, use the Confluence/wiki artifacts to publish "
                    "a durable team runbook."
                ),
                inputs=["confluence_page.json", "wiki_page.md"],
                expected_output="A published or proposed documentation update.",
                safety_notes=[
                    "Do not overwrite existing team docs without review.",
                    "Keep generated pages traceable to snapshot and generation time.",
                ],
            ),
        ]
