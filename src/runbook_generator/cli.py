"""Command line interface for runbook generation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from runbook_generator.agent.observability import ObservabilityConfig
from runbook_generator.agent.workflow import AgentOpsWorkflow
from runbook_generator.collectors.aws import AwsCliCollector
from runbook_generator.collectors.base import CollectionTarget, Collector
from runbook_generator.collectors.fixture import FixtureCollector
from runbook_generator.collectors.kubernetes import KubectlCollector
from runbook_generator.config import SUPPORTED_SOURCES, load_runtime_config
from runbook_generator.exporters.confluence import ConfluenceTarget
from runbook_generator.exporters.jira import JiraTarget
from runbook_generator.exporters.slack import SlackTarget
from runbook_generator.exporters.wiki import WikiTarget
from runbook_generator.orchestrator import RunbookGenerator


def build_parser() -> argparse.ArgumentParser:
    config = load_runtime_config()
    parser = argparse.ArgumentParser(
        prog="runbook-generator",
        description="Generate operational runbooks from AWS, EKS, Kubernetes, or fixture snapshots.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    generate = subcommands.add_parser(
        "generate",
        help="Collect environment data and render a Markdown runbook.",
    )
    generate.add_argument(
        "--source",
        choices=SUPPORTED_SOURCES,
        default=config.source,
        help=(
            "Data source. Use 'eks' for AWS EKS control-plane plus kubectl workload discovery."
        ),
    )
    generate.add_argument("--environment", default=config.environment)
    generate.add_argument(
        "--account",
        default=config.account,
        help="Expected cloud account identifier.",
    )
    generate.add_argument(
        "--region",
        default=config.region,
        help="AWS region. Defaults to RUNBOOK_AWS_REGION, AWS_REGION, or AWS_DEFAULT_REGION.",
    )
    generate.add_argument(
        "--cluster",
        default=config.cluster,
        help="EKS/Kubernetes cluster name.",
    )
    generate.add_argument(
        "--namespace",
        default=config.namespace,
        help="Kubernetes namespace.",
    )
    generate.add_argument(
        "--service",
        default=config.service,
        help="Primary service/workload name.",
    )
    generate.add_argument(
        "--kube-context",
        default=config.kube_context,
        help="kubectl context to query.",
    )
    generate.add_argument(
        "--output",
        "-o",
        default=config.output,
        help="Path for the generated Markdown runbook. Prints to stdout when omitted.",
    )
    generate.add_argument(
        "--snapshot-output",
        default=config.snapshot_output,
        help="Optional path for the normalized JSON snapshot used to render the runbook.",
    )
    generate.add_argument(
        "--print-snapshot",
        action="store_true",
        help="Print the normalized JSON snapshot after the runbook.",
    )

    ops_package = subcommands.add_parser(
        "ops-package",
        help=(
            "Generate a runbook plus agent, incident-management, "
            "Confluence, Jira, and wiki artifacts."
        ),
    )
    _add_collection_arguments(ops_package, config)
    ops_package.add_argument(
        "--output-dir",
        default=config.agent_output_dir,
        help="Directory for generated agent/reporting artifacts.",
    )
    ops_package.add_argument(
        "--observability-provider",
        default=config.observability_provider,
        help="Monitoring provider name, for example prometheus, grafana, or datadog.",
    )
    ops_package.add_argument(
        "--observability-base-url",
        default=config.observability_base_url,
        help="Base URL for the observability platform.",
    )
    ops_package.add_argument(
        "--observability-query",
        default=config.observability_query,
        help="Query used to collect or describe monitoring signals.",
    )
    ops_package.add_argument(
        "--observability-dashboard-url",
        default=config.observability_dashboard_url,
        help="Dashboard URL to include in generated reports.",
    )
    ops_package.add_argument(
        "--confluence-base-url",
        default=config.confluence_base_url,
        help="Confluence base URL for generated page payload metadata.",
    )
    ops_package.add_argument(
        "--confluence-space-key",
        default=config.confluence_space_key,
        help="Confluence space key for generated page payload metadata.",
    )
    ops_package.add_argument(
        "--confluence-parent-page-id",
        default=config.confluence_parent_page_id,
        help="Optional parent page ID for generated Confluence payloads.",
    )
    ops_package.add_argument(
        "--jira-base-url",
        default=config.jira_base_url,
        help="Jira base URL for generated issue payload metadata.",
    )
    ops_package.add_argument(
        "--jira-project-key",
        default=config.jira_project_key,
        help="Jira project key for generated issue payload metadata.",
    )
    ops_package.add_argument(
        "--jira-issue-type",
        default=config.jira_issue_type,
        help="Jira issue type for generated incident payloads.",
    )
    ops_package.add_argument(
        "--wiki-base-url",
        default=config.wiki_base_url,
        help="Generic wiki base URL for generated wiki page metadata.",
    )
    ops_package.add_argument(
        "--slack-webhook-url",
        default=config.slack_webhook_url,
        help="Slack incoming webhook URL. Required only when sending.",
    )
    ops_package.add_argument(
        "--slack-channel",
        default=config.slack_channel,
        help="Slack channel override for generated notifications.",
    )
    ops_package.add_argument(
        "--slack-username",
        default=config.slack_username,
        help="Slack bot username for generated notifications.",
    )
    ops_package.add_argument(
        "--send-slack",
        action="store_true",
        default=config.slack_send,
        help="Send the Slack notification via webhook instead of dry-run only.",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "generate":
        target = _target_from_args(args)
        generator = RunbookGenerator(_collectors_for_source(args.source))
        snapshot, runbook = generator.generate(target)

        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(runbook, encoding="utf-8")
        else:
            print(runbook, end="")

        snapshot_json = json.dumps(snapshot.to_dict(), indent=2, sort_keys=True)
        if args.snapshot_output:
            snapshot_path = Path(args.snapshot_output)
            snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            snapshot_path.write_text(snapshot_json + "\n", encoding="utf-8")
        if args.print_snapshot:
            print(snapshot_json)
        return 0

    if args.command == "ops-package":
        target = _target_from_args(args)
        generator = RunbookGenerator(_collectors_for_source(args.source))
        snapshot, runbook = generator.generate(target)
        output_dir = Path(args.output_dir)
        artifacts = AgentOpsWorkflow().create_package(
            snapshot=snapshot,
            runbook=runbook,
            output_dir=output_dir,
            observability_config=ObservabilityConfig(
                provider=args.observability_provider,
                base_url=args.observability_base_url,
                query=args.observability_query,
                dashboard_url=args.observability_dashboard_url,
            ),
            confluence_target=ConfluenceTarget(
                base_url=args.confluence_base_url,
                space_key=args.confluence_space_key,
                parent_page_id=args.confluence_parent_page_id,
            ),
            jira_target=JiraTarget(
                base_url=args.jira_base_url,
                project_key=args.jira_project_key,
                issue_type=args.jira_issue_type,
            ),
            slack_target=SlackTarget(
                webhook_url=args.slack_webhook_url,
                channel=args.slack_channel,
                username=args.slack_username,
                send=args.send_slack,
            ),
            wiki_target=WikiTarget(base_url=args.wiki_base_url),
        )
        print(json.dumps(artifacts, indent=2, sort_keys=True))
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2


def _add_collection_arguments(
    parser: argparse.ArgumentParser,
    config: object,
) -> None:
    parser.add_argument(
        "--source",
        choices=SUPPORTED_SOURCES,
        default=config.source,
        help=(
            "Data source. Use 'eks' for AWS EKS control-plane plus kubectl workload discovery."
        ),
    )
    parser.add_argument("--environment", default=config.environment)
    parser.add_argument(
        "--account",
        default=config.account,
        help="Expected cloud account identifier.",
    )
    parser.add_argument(
        "--region",
        default=config.region,
        help="AWS region. Defaults to RUNBOOK_AWS_REGION, AWS_REGION, or AWS_DEFAULT_REGION.",
    )
    parser.add_argument(
        "--cluster",
        default=config.cluster,
        help="EKS/Kubernetes cluster name.",
    )
    parser.add_argument(
        "--namespace",
        default=config.namespace,
        help="Kubernetes namespace.",
    )
    parser.add_argument(
        "--service",
        default=config.service,
        help="Primary service/workload name.",
    )
    parser.add_argument(
        "--kube-context",
        default=config.kube_context,
        help="kubectl context to query.",
    )


def _target_from_args(args: argparse.Namespace) -> CollectionTarget:
    return CollectionTarget(
        environment=args.environment,
        account=args.account,
        region=args.region,
        cluster=args.cluster,
        namespace=args.namespace,
        service=args.service,
        kube_context=args.kube_context,
    )


def _collectors_for_source(source: str) -> list[Collector]:
    if source == "fixture":
        return [FixtureCollector()]
    if source == "aws":
        return [AwsCliCollector(include_eks=True)]
    if source == "eks":
        return [AwsCliCollector(include_eks=True), KubectlCollector()]
    if source == "kubernetes":
        return [KubectlCollector()]
    raise ValueError(f"Unsupported source: {source}")


if __name__ == "__main__":
    raise SystemExit(main())
