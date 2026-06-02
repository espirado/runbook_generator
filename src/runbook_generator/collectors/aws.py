"""AWS CLI backed collector for account, regional, and EKS inventory."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Any

from runbook_generator.collectors.base import CollectionTarget
from runbook_generator.models import EnvironmentSnapshot, OperationalCheck, Resource


class AwsCliCollector:
    """Collect AWS inventory by shelling out to the authenticated AWS CLI."""

    name = "aws"

    def __init__(self, include_eks: bool = True) -> None:
        self.include_eks = include_eks

    def collect(self, target: CollectionTarget) -> EnvironmentSnapshot:
        region = target.region or os.environ.get("AWS_REGION")
        warnings: list[str] = []
        snapshot = EnvironmentSnapshot(
            name=target.environment,
            providers=["aws"],
            account=target.account,
            region=region,
            warnings=warnings,
            metadata={"collector": self.name},
        )

        if shutil.which("aws") is None:
            snapshot.add_warning(
                "AWS CLI was not found. Install/configure aws to collect live AWS inventory."
            )
            return snapshot

        if not region:
            region = self._run_text(["aws", "configure", "get", "region"], warnings)
            region = region or None
            snapshot.region = region

        identity = self._run_json(["aws", "sts", "get-caller-identity"], warnings)
        if isinstance(identity, dict):
            snapshot.account = snapshot.account or identity.get("Account")
            if arn := identity.get("Arn"):
                snapshot.metadata["caller_arn"] = arn

        self._collect_ec2(snapshot, target, warnings)
        self._collect_lambda(snapshot, target, warnings)
        self._collect_rds(snapshot, target, warnings)
        self._collect_elbv2(snapshot, target, warnings)
        self._collect_cloudwatch_alarms(snapshot, target, warnings)

        if self.include_eks:
            self._collect_eks(snapshot, target, warnings)

        snapshot.checks.extend(self._aws_checks(snapshot.region))
        return snapshot

    def _collect_ec2(
        self,
        snapshot: EnvironmentSnapshot,
        target: CollectionTarget,
        warnings: list[str],
    ) -> None:
        data = self._run_json(
            self._region_args(["aws", "ec2", "describe-instances"], target),
            warnings,
        )
        if not isinstance(data, dict):
            return

        for reservation in data.get("Reservations", []):
            for instance in reservation.get("Instances", []):
                instance_id = instance.get("InstanceId")
                if not instance_id:
                    continue
                name = self._tag_value(instance.get("Tags", []), "Name") or instance_id
                snapshot.add_resource(
                    Resource(
                        id=f"aws:ec2:{snapshot.region}:{instance_id}",
                        name=name,
                        kind="compute.vm",
                        provider="aws.ec2",
                        environment=target.environment,
                        region=snapshot.region,
                        status=instance.get("State", {}).get("Name"),
                        attributes={
                            "instance_id": instance_id,
                            "instance_type": instance.get("InstanceType"),
                            "private_ip": instance.get("PrivateIpAddress"),
                            "public_ip": instance.get("PublicIpAddress"),
                            "subnet_id": instance.get("SubnetId"),
                            "vpc_id": instance.get("VpcId"),
                            "launch_time": str(instance.get("LaunchTime", "")),
                        },
                    )
                )

    def _collect_lambda(
        self,
        snapshot: EnvironmentSnapshot,
        target: CollectionTarget,
        warnings: list[str],
    ) -> None:
        data = self._run_json(
            self._region_args(["aws", "lambda", "list-functions"], target),
            warnings,
        )
        if not isinstance(data, dict):
            return

        for function in data.get("Functions", []):
            name = function.get("FunctionName")
            if not name:
                continue
            snapshot.add_resource(
                Resource(
                    id=function.get("FunctionArn") or f"aws:lambda:{snapshot.region}:{name}",
                    name=name,
                    kind="compute.serverless_function",
                    provider="aws.lambda",
                    environment=target.environment,
                    region=snapshot.region,
                    status=function.get("State") or "unknown",
                    attributes={
                        "runtime": function.get("Runtime"),
                        "handler": function.get("Handler"),
                        "memory_size": function.get("MemorySize"),
                        "timeout": function.get("Timeout"),
                        "last_modified": function.get("LastModified"),
                    },
                )
            )

    def _collect_rds(
        self,
        snapshot: EnvironmentSnapshot,
        target: CollectionTarget,
        warnings: list[str],
    ) -> None:
        data = self._run_json(
            self._region_args(["aws", "rds", "describe-db-instances"], target),
            warnings,
        )
        if not isinstance(data, dict):
            return

        for db in data.get("DBInstances", []):
            identifier = db.get("DBInstanceIdentifier")
            if not identifier:
                continue
            snapshot.add_resource(
                Resource(
                    id=db.get("DBInstanceArn")
                    or f"aws:rds:{snapshot.region}:{identifier}",
                    name=identifier,
                    kind="data.database",
                    provider="aws.rds",
                    environment=target.environment,
                    region=snapshot.region,
                    status=db.get("DBInstanceStatus"),
                    attributes={
                        "engine": db.get("Engine"),
                        "engine_version": db.get("EngineVersion"),
                        "multi_az": db.get("MultiAZ"),
                        "storage_type": db.get("StorageType"),
                        "endpoint": (db.get("Endpoint") or {}).get("Address"),
                    },
                )
            )

    def _collect_elbv2(
        self,
        snapshot: EnvironmentSnapshot,
        target: CollectionTarget,
        warnings: list[str],
    ) -> None:
        data = self._run_json(
            self._region_args(["aws", "elbv2", "describe-load-balancers"], target),
            warnings,
        )
        if not isinstance(data, dict):
            return

        for load_balancer in data.get("LoadBalancers", []):
            arn = load_balancer.get("LoadBalancerArn")
            name = load_balancer.get("LoadBalancerName")
            if not arn or not name:
                continue
            snapshot.add_resource(
                Resource(
                    id=arn,
                    name=name,
                    kind="network.load_balancer",
                    provider="aws.elbv2",
                    environment=target.environment,
                    region=snapshot.region,
                    status=load_balancer.get("State", {}).get("Code"),
                    attributes={
                        "dns_name": load_balancer.get("DNSName"),
                        "scheme": load_balancer.get("Scheme"),
                        "type": load_balancer.get("Type"),
                        "vpc_id": load_balancer.get("VpcId"),
                        "availability_zones": [
                            zone.get("ZoneName")
                            for zone in load_balancer.get("AvailabilityZones", [])
                        ],
                    },
                )
            )

    def _collect_cloudwatch_alarms(
        self,
        snapshot: EnvironmentSnapshot,
        target: CollectionTarget,
        warnings: list[str],
    ) -> None:
        data = self._run_json(
            self._region_args(["aws", "cloudwatch", "describe-alarms"], target),
            warnings,
        )
        if not isinstance(data, dict):
            return

        for alarm in data.get("MetricAlarms", []):
            name = alarm.get("AlarmName")
            if not name:
                continue
            snapshot.add_resource(
                Resource(
                    id=alarm.get("AlarmArn")
                    or f"aws:cloudwatch:{snapshot.region}:{name}",
                    name=name,
                    kind="observability.alert",
                    provider="aws.cloudwatch",
                    environment=target.environment,
                    region=snapshot.region,
                    status=alarm.get("StateValue"),
                    attributes={
                        "metric_name": alarm.get("MetricName"),
                        "namespace": alarm.get("Namespace"),
                        "comparison_operator": alarm.get("ComparisonOperator"),
                        "threshold": alarm.get("Threshold"),
                        "period": alarm.get("Period"),
                    },
                )
            )

    def _collect_eks(
        self,
        snapshot: EnvironmentSnapshot,
        target: CollectionTarget,
        warnings: list[str],
    ) -> None:
        clusters = [target.cluster] if target.cluster else []
        if not clusters:
            data = self._run_json(
                self._region_args(["aws", "eks", "list-clusters"], target),
                warnings,
            )
            if isinstance(data, dict):
                clusters = data.get("clusters", [])

        if clusters and "aws.eks" not in snapshot.providers:
            snapshot.providers.append("aws.eks")

        for cluster_name in clusters:
            if not cluster_name:
                continue
            data = self._run_json(
                self._region_args(
                    ["aws", "eks", "describe-cluster", "--name", cluster_name],
                    target,
                ),
                warnings,
            )
            if not isinstance(data, dict):
                continue
            cluster = data.get("cluster", {})
            snapshot.add_resource(
                Resource(
                    id=cluster.get("arn")
                    or f"aws:eks:{snapshot.region}:{cluster_name}",
                    name=cluster_name,
                    kind="compute.cluster",
                    provider="aws.eks",
                    environment=target.environment,
                    region=snapshot.region,
                    status=cluster.get("status"),
                    attributes={
                        "version": cluster.get("version"),
                        "platform_version": cluster.get("platformVersion"),
                        "endpoint": cluster.get("endpoint"),
                        "role_arn": cluster.get("roleArn"),
                        "vpc_id": (cluster.get("resourcesVpcConfig") or {}).get(
                            "vpcId"
                        ),
                        "endpoint_public_access": (
                            cluster.get("resourcesVpcConfig") or {}
                        ).get("endpointPublicAccess"),
                    },
                )
            )
            self._collect_eks_nodegroups(snapshot, target, cluster_name, warnings)

    def _collect_eks_nodegroups(
        self,
        snapshot: EnvironmentSnapshot,
        target: CollectionTarget,
        cluster_name: str,
        warnings: list[str],
    ) -> None:
        data = self._run_json(
            self._region_args(
                ["aws", "eks", "list-nodegroups", "--cluster-name", cluster_name],
                target,
            ),
            warnings,
        )
        if not isinstance(data, dict):
            return

        for nodegroup_name in data.get("nodegroups", []):
            detail = self._run_json(
                self._region_args(
                    [
                        "aws",
                        "eks",
                        "describe-nodegroup",
                        "--cluster-name",
                        cluster_name,
                        "--nodegroup-name",
                        nodegroup_name,
                    ],
                    target,
                ),
                warnings,
            )
            if not isinstance(detail, dict):
                continue
            nodegroup = detail.get("nodegroup", {})
            snapshot.add_resource(
                Resource(
                    id=nodegroup.get("nodegroupArn")
                    or f"aws:eks:{snapshot.region}:{cluster_name}:nodegroup/{nodegroup_name}",
                    name=nodegroup_name,
                    kind="compute.node_group",
                    provider="aws.eks",
                    environment=target.environment,
                    region=snapshot.region,
                    status=nodegroup.get("status"),
                    attributes={
                        "cluster": cluster_name,
                        "capacity_type": nodegroup.get("capacityType"),
                        "instance_types": nodegroup.get("instanceTypes", []),
                        "scaling_config": nodegroup.get("scalingConfig", {}),
                        "release_version": nodegroup.get("releaseVersion"),
                    },
                )
            )

    def _aws_checks(self, region: str | None) -> list[OperationalCheck]:
        region_flag = f" --region {region}" if region else ""
        return [
            OperationalCheck(
                title="List active CloudWatch alarms",
                command=f"aws cloudwatch describe-alarms{region_flag} --state-value ALARM",
                description="Start here when the generated runbook shows AWS resources.",
            ),
            OperationalCheck(
                title="Confirm AWS caller identity",
                command="aws sts get-caller-identity",
                description="Verifies the account context used for live discovery.",
            ),
        ]

    def _region_args(
        self,
        args: list[str],
        target: CollectionTarget,
    ) -> list[str]:
        region = target.region or os.environ.get("AWS_REGION")
        if region and "--region" not in args:
            return [*args, "--region", region]
        return args

    def _run_json(self, args: list[str], warnings: list[str]) -> Any:
        output = self._run_text(args, warnings)
        if not output:
            return None
        try:
            return json.loads(output)
        except json.JSONDecodeError as exc:
            warnings.append(f"Command returned non-JSON output: {' '.join(args)}: {exc}")
            return None

    def _run_text(self, args: list[str], warnings: list[str]) -> str | None:
        try:
            result = subprocess.run(
                args,
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            warnings.append(f"Command not found: {args[0]}")
            return None
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            warnings.append(
                f"Command failed: {' '.join(args)}"
                + (f" ({stderr})" if stderr else "")
            )
            return None
        return result.stdout.strip()

    @staticmethod
    def _tag_value(tags: list[dict[str, Any]], key: str) -> str | None:
        for tag in tags:
            if tag.get("Key") == key:
                return tag.get("Value")
        return None
