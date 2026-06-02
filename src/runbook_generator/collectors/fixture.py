"""Offline fixture collector used for demos and tests."""

from __future__ import annotations

from runbook_generator.collectors.base import CollectionTarget
from runbook_generator.config import (
    DEFAULT_FIXTURE_ACCOUNT,
    DEFAULT_FIXTURE_ALARM,
    DEFAULT_FIXTURE_CLUSTER,
    DEFAULT_FIXTURE_DATABASE,
    DEFAULT_FIXTURE_IMAGE,
    DEFAULT_FIXTURE_NAMESPACE,
    DEFAULT_FIXTURE_REGION,
    DEFAULT_FIXTURE_SERVICE,
)
from runbook_generator.models import (
    EnvironmentSnapshot,
    OperationalCheck,
    Relationship,
    Resource,
)


class FixtureCollector:
    """Return an AWS/EKS-shaped snapshot without requiring live credentials."""

    name = "fixture"

    def collect(self, target: CollectionTarget) -> EnvironmentSnapshot:
        environment = target.environment
        region = target.region or DEFAULT_FIXTURE_REGION
        cluster_name = target.cluster or DEFAULT_FIXTURE_CLUSTER
        namespace = target.namespace or DEFAULT_FIXTURE_NAMESPACE
        service_name = target.service or DEFAULT_FIXTURE_SERVICE
        database_name = f"{service_name}-{DEFAULT_FIXTURE_DATABASE}"
        alarm_name = f"{service_name}-{DEFAULT_FIXTURE_ALARM}"

        eks_cluster = Resource(
            id=f"aws:eks:{region}:{cluster_name}",
            name=cluster_name,
            kind="compute.cluster",
            provider="aws.eks",
            environment=environment,
            region=region,
            status="ACTIVE",
            attributes={
                "platform_version": "eks.8",
                "endpoint_public_access": True,
                "namespace": namespace,
            },
        )
        workload = Resource(
            id=f"k8s:{cluster_name}:{namespace}:deployment/{service_name}",
            name=service_name,
            kind="compute.workload",
            provider="kubernetes",
            environment=environment,
            region=region,
            status="Available",
            attributes={
                "namespace": namespace,
                "replicas": 3,
                "ready_replicas": 3,
                "image": DEFAULT_FIXTURE_IMAGE,
            },
        )
        service = Resource(
            id=f"k8s:{cluster_name}:{namespace}:service/{service_name}",
            name=service_name,
            kind="network.endpoint",
            provider="kubernetes",
            environment=environment,
            region=region,
            status="ClusterIP",
            attributes={
                "namespace": namespace,
                "ports": ["http:80->8080"],
                "selector": {"app": service_name},
            },
        )
        database = Resource(
            id=f"aws:rds:{region}:{database_name}",
            name=database_name,
            kind="data.database",
            provider="aws.rds",
            environment=environment,
            region=region,
            status="available",
            attributes={"engine": "postgres", "multi_az": True},
        )
        alarm = Resource(
            id=f"aws:cloudwatch:{region}:{alarm_name}",
            name=alarm_name,
            kind="observability.alert",
            provider="aws.cloudwatch",
            environment=environment,
            region=region,
            status="OK",
            attributes={"metric": "HTTPCode_Target_5XX_Count"},
        )

        return EnvironmentSnapshot(
            name=environment,
            providers=["aws", "aws.eks", "kubernetes"],
            account=target.account or DEFAULT_FIXTURE_ACCOUNT,
            region=region,
            resources=[eks_cluster, workload, service, database, alarm],
            relationships=[
                Relationship(
                    source_id=workload.id,
                    target_id=eks_cluster.id,
                    relationship_type="runs_on",
                    description="Kubernetes deployment runs on the EKS cluster.",
                ),
                Relationship(
                    source_id=service.id,
                    target_id=workload.id,
                    relationship_type="routes_to",
                    description="Kubernetes Service selects the deployment pods.",
                ),
                Relationship(
                    source_id=workload.id,
                    target_id=database.id,
                    relationship_type="depends_on",
                    description="Application stores transactional data in RDS.",
                ),
                Relationship(
                    source_id=alarm.id,
                    target_id=service.id,
                    relationship_type="monitors",
                    description="CloudWatch alarm tracks service 5xx errors.",
                ),
            ],
            checks=[
                OperationalCheck(
                    title="Check deployment rollout",
                    command=(
                        f"kubectl rollout status deployment/{service_name} "
                        f"-n {namespace}"
                    ),
                    description="Confirms the Kubernetes deployment is healthy.",
                ),
                OperationalCheck(
                    title="Inspect recent warning events",
                    command=(
                        f"kubectl get events -n {namespace} "
                        "--field-selector type=Warning --sort-by=.lastTimestamp"
                    ),
                    description="Surfaces failed scheduling, probe, and image pulls.",
                ),
                OperationalCheck(
                    title="Review active CloudWatch alarms",
                    command=(
                        f"aws cloudwatch describe-alarms --region {region} "
                        "--state-value ALARM"
                    ),
                    description="Finds AWS-side symptoms affecting the service.",
                ),
            ],
            warnings=[
                "Fixture data is representative only; run with --source eks for live inventory.",
                "Owner and escalation metadata were not discovered in the fixture.",
            ],
        )
