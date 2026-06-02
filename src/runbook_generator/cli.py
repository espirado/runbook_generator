"""Command line interface for runbook generation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from runbook_generator.collectors.aws import AwsCliCollector
from runbook_generator.collectors.base import CollectionTarget, Collector
from runbook_generator.collectors.fixture import FixtureCollector
from runbook_generator.collectors.kubernetes import KubectlCollector
from runbook_generator.orchestrator import RunbookGenerator


def build_parser() -> argparse.ArgumentParser:
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
        choices=["fixture", "aws", "eks", "kubernetes"],
        default="fixture",
        help=(
            "Data source. Use 'eks' for AWS EKS control-plane plus kubectl workload discovery."
        ),
    )
    generate.add_argument("--environment", default="production")
    generate.add_argument("--account", help="Expected cloud account identifier.")
    generate.add_argument("--region", help="AWS region, for example us-east-1.")
    generate.add_argument("--cluster", help="EKS/Kubernetes cluster name.")
    generate.add_argument("--namespace", help="Kubernetes namespace.")
    generate.add_argument("--service", help="Primary service/workload name.")
    generate.add_argument("--kube-context", help="kubectl context to query.")
    generate.add_argument(
        "--output",
        "-o",
        help="Path for the generated Markdown runbook. Prints to stdout when omitted.",
    )
    generate.add_argument(
        "--snapshot-output",
        help="Optional path for the normalized JSON snapshot used to render the runbook.",
    )
    generate.add_argument(
        "--print-snapshot",
        action="store_true",
        help="Print the normalized JSON snapshot after the runbook.",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "generate":
        target = CollectionTarget(
            environment=args.environment,
            account=args.account,
            region=args.region,
            cluster=args.cluster,
            namespace=args.namespace,
            service=args.service,
            kube_context=args.kube_context,
        )
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

    parser.error(f"Unsupported command: {args.command}")
    return 2


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
