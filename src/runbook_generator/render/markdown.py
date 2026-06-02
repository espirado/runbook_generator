"""Markdown renderer for normalized operational snapshots."""

from __future__ import annotations

from collections import defaultdict

from runbook_generator.models import EnvironmentSnapshot, Resource


class MarkdownRunbookRenderer:
    """Render deterministic Markdown runbooks from environment snapshots."""

    def render(self, snapshot: EnvironmentSnapshot) -> str:
        lines: list[str] = [
            f"# Operational Runbook: {snapshot.name}",
            "",
            "## Summary",
            "",
            f"- Generated at: `{snapshot.generated_at}`",
            f"- Providers: `{', '.join(snapshot.providers) or 'unknown'}`",
            f"- Account: `{snapshot.account or 'unknown'}`",
            f"- Region: `{snapshot.region or 'unknown'}`",
            f"- Resources discovered: `{len(snapshot.resources)}`",
            "",
        ]

        if snapshot.warnings:
            lines.extend(["## Discovery warnings", ""])
            for warning in snapshot.warnings:
                lines.append(f"- {warning}")
            lines.append("")

        lines.extend(self._resource_inventory(snapshot))
        lines.extend(self._relationships(snapshot))
        lines.extend(self._health_and_debugging(snapshot))
        lines.extend(self._failure_modes(snapshot))
        lines.extend(self._recovery(snapshot))
        lines.extend(self._ownership_gaps(snapshot))
        return "\n".join(lines).rstrip() + "\n"

    def _resource_inventory(self, snapshot: EnvironmentSnapshot) -> list[str]:
        lines = ["## Resource inventory", ""]
        if not snapshot.resources:
            return [*lines, "No resources were discovered.", ""]

        resources_by_kind: dict[str, list[Resource]] = defaultdict(list)
        for resource in snapshot.resources:
            resources_by_kind[resource.kind].append(resource)

        for kind in sorted(resources_by_kind):
            lines.extend([f"### {kind}", ""])
            lines.append("| Name | Provider | Status | Region | Key details |")
            lines.append("| --- | --- | --- | --- | --- |")
            for resource in sorted(resources_by_kind[kind], key=lambda item: item.name):
                lines.append(
                    "| "
                    + " | ".join(
                        [
                            self._escape(resource.name),
                            self._escape(resource.provider),
                            self._escape(resource.status or "unknown"),
                            self._escape(resource.region or "unknown"),
                            self._escape(self._key_details(resource)),
                        ]
                    )
                    + " |"
                )
            lines.append("")
        return lines

    def _relationships(self, snapshot: EnvironmentSnapshot) -> list[str]:
        lines = ["## Dependency and routing map", ""]
        if not snapshot.relationships:
            return [
                *lines,
                "No relationships were inferred yet. Add tags, service selectors, or collector-specific dependency mapping to improve this section.",
                "",
            ]

        resource_names = {resource.id: resource.name for resource in snapshot.resources}
        for relationship in snapshot.relationships:
            source = resource_names.get(relationship.source_id, relationship.source_id)
            target = resource_names.get(relationship.target_id, relationship.target_id)
            description = (
                f" - {relationship.description}"
                if relationship.description
                else ""
            )
            lines.append(
                f"- `{source}` **{relationship.relationship_type}** `{target}`{description}"
            )
        lines.append("")
        return lines

    def _health_and_debugging(self, snapshot: EnvironmentSnapshot) -> list[str]:
        lines = ["## Health checks and debugging commands", ""]
        if not snapshot.checks:
            return [
                *lines,
                "- No collector-specific checks were produced.",
                "",
            ]

        for check in snapshot.checks:
            lines.append(f"### {check.title}")
            lines.append("")
            if check.description:
                lines.append(check.description)
                lines.append("")
            if check.command:
                lines.extend(["```bash", check.command, "```", ""])
        return lines

    def _failure_modes(self, snapshot: EnvironmentSnapshot) -> list[str]:
        kinds = {resource.kind for resource in snapshot.resources}
        lines = ["## Likely failure modes", ""]
        if "compute.workload" in kinds:
            lines.extend(
                [
                    "- Kubernetes rollout stuck, CrashLoopBackOff, failed probes, image pull failures, or pending pods.",
                    "- Node pressure or unavailable EKS node groups reducing schedulable capacity.",
                ]
            )
        if "compute.vm" in kinds:
            lines.append("- EC2 instance health check failures, exhausted disk, or unreachable hosts.")
        if "compute.serverless_function" in kinds:
            lines.append("- Lambda timeout, throttling, cold-start latency, or permission failures.")
        if "data.database" in kinds:
            lines.append("- Database connection saturation, storage pressure, failover, or slow queries.")
        if "network.load_balancer" in kinds or "network.ingress" in kinds:
            lines.append("- Load balancer target health degradation, DNS issues, or ingress misconfiguration.")
        if "observability.alert" in kinds:
            lines.append("- Active CloudWatch alarms indicate degraded dependencies or service symptoms.")
        if len(lines) == 2:
            lines.append("- No resource-specific failure modes could be inferred from the current snapshot.")
        lines.append("")
        return lines

    def _recovery(self, snapshot: EnvironmentSnapshot) -> list[str]:
        lines = [
            "## Recovery playbook",
            "",
            "1. Confirm account, region, cluster, and namespace before running commands.",
            "2. Check active alerts and recent events to identify the failing layer.",
            "3. Validate the serving path: DNS/load balancer -> endpoint/service -> workload/function/VM -> data dependencies.",
            "4. Prefer rollout rollback or scaling actions over destructive changes.",
            "5. Escalate when ownership, data restore, IAM, or network boundary changes are required.",
            "",
        ]
        return lines

    def _ownership_gaps(self, snapshot: EnvironmentSnapshot) -> list[str]:
        unowned = [resource for resource in snapshot.resources if not resource.owner]
        if not unowned:
            return ["## Ownership and escalation", "", "All discovered resources include owner metadata.", ""]
        lines = [
            "## Ownership and escalation",
            "",
            "Owner metadata was not discovered for these resources. Add tags/labels such as `owner`, `team`, or `pager` so future runbooks can route incidents faster.",
            "",
        ]
        for resource in unowned[:20]:
            lines.append(f"- `{resource.name}` ({resource.provider}, {resource.kind})")
        if len(unowned) > 20:
            lines.append(f"- ...and {len(unowned) - 20} more")
        lines.append("")
        return lines

    @staticmethod
    def _key_details(resource: Resource) -> str:
        interesting_keys = [
            "namespace",
            "replicas",
            "ready_replicas",
            "engine",
            "runtime",
            "dns_name",
            "instance_type",
            "metric_name",
            "version",
        ]
        details = []
        for key in interesting_keys:
            value = resource.attributes.get(key)
            if value not in (None, "", [], {}):
                details.append(f"{key}={value}")
        return ", ".join(details) if details else "-"

    @staticmethod
    def _escape(value: str) -> str:
        return value.replace("|", "\\|").replace("\n", " ")
