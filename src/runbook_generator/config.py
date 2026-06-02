"""Runtime configuration variables for live environment discovery."""

from __future__ import annotations

import os
from dataclasses import dataclass


ENV_SOURCE = "RUNBOOK_SOURCE"
ENV_ENVIRONMENT = "RUNBOOK_ENVIRONMENT"
ENV_AWS_ACCOUNT = "RUNBOOK_AWS_ACCOUNT"
ENV_AWS_REGION = "RUNBOOK_AWS_REGION"
ENV_EKS_CLUSTER = "RUNBOOK_EKS_CLUSTER"
ENV_K8S_NAMESPACE = "RUNBOOK_K8S_NAMESPACE"
ENV_SERVICE = "RUNBOOK_SERVICE"
ENV_KUBE_CONTEXT = "RUNBOOK_KUBE_CONTEXT"
ENV_OUTPUT = "RUNBOOK_OUTPUT"
ENV_SNAPSHOT_OUTPUT = "RUNBOOK_SNAPSHOT_OUTPUT"

DEFAULT_SOURCE = "fixture"
DEFAULT_ENVIRONMENT = "unknown"
SUPPORTED_SOURCES = ("fixture", "aws", "eks", "kubernetes")

DEFAULT_FIXTURE_ACCOUNT = "000000000000"
DEFAULT_FIXTURE_REGION = "local"
DEFAULT_FIXTURE_CLUSTER = "fixture-cluster"
DEFAULT_FIXTURE_NAMESPACE = "fixture-namespace"
DEFAULT_FIXTURE_SERVICE = "fixture-service"
DEFAULT_FIXTURE_IMAGE = "example.invalid/runbook-generator/fixture-service:latest"
DEFAULT_FIXTURE_DATABASE = "fixture-database"
DEFAULT_FIXTURE_ALARM = "fixture-service-alarm"


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    """CLI defaults loaded from environment variables."""

    source: str
    environment: str
    account: str | None
    region: str | None
    cluster: str | None
    namespace: str | None
    service: str | None
    kube_context: str | None
    output: str | None
    snapshot_output: str | None


def load_runtime_config() -> RuntimeConfig:
    """Load user-provided defaults without hardcoding live AWS/EKS details."""

    return RuntimeConfig(
        source=os.environ.get(ENV_SOURCE, DEFAULT_SOURCE),
        environment=os.environ.get(ENV_ENVIRONMENT, DEFAULT_ENVIRONMENT),
        account=os.environ.get(ENV_AWS_ACCOUNT),
        region=(
            os.environ.get(ENV_AWS_REGION)
            or os.environ.get("AWS_REGION")
            or os.environ.get("AWS_DEFAULT_REGION")
        ),
        cluster=os.environ.get(ENV_EKS_CLUSTER),
        namespace=os.environ.get(ENV_K8S_NAMESPACE),
        service=os.environ.get(ENV_SERVICE),
        kube_context=os.environ.get(ENV_KUBE_CONTEXT),
        output=os.environ.get(ENV_OUTPUT),
        snapshot_output=os.environ.get(ENV_SNAPSHOT_OUTPUT),
    )
