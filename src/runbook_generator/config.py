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
ENV_AGENT_OUTPUT_DIR = "RUNBOOK_AGENT_OUTPUT_DIR"
ENV_OBSERVABILITY_PROVIDER = "RUNBOOK_OBSERVABILITY_PROVIDER"
ENV_OBSERVABILITY_BASE_URL = "RUNBOOK_OBSERVABILITY_BASE_URL"
ENV_OBSERVABILITY_QUERY = "RUNBOOK_OBSERVABILITY_QUERY"
ENV_OBSERVABILITY_DASHBOARD_URL = "RUNBOOK_OBSERVABILITY_DASHBOARD_URL"
ENV_CONFLUENCE_BASE_URL = "RUNBOOK_CONFLUENCE_BASE_URL"
ENV_CONFLUENCE_SPACE_KEY = "RUNBOOK_CONFLUENCE_SPACE_KEY"
ENV_CONFLUENCE_PARENT_PAGE_ID = "RUNBOOK_CONFLUENCE_PARENT_PAGE_ID"
ENV_JIRA_BASE_URL = "RUNBOOK_JIRA_BASE_URL"
ENV_JIRA_PROJECT_KEY = "RUNBOOK_JIRA_PROJECT_KEY"
ENV_JIRA_ISSUE_TYPE = "RUNBOOK_JIRA_ISSUE_TYPE"
ENV_WIKI_BASE_URL = "RUNBOOK_WIKI_BASE_URL"
ENV_SLACK_WEBHOOK_URL = "RUNBOOK_SLACK_WEBHOOK_URL"
ENV_SLACK_CHANNEL = "RUNBOOK_SLACK_CHANNEL"
ENV_SLACK_USERNAME = "RUNBOOK_SLACK_USERNAME"
ENV_SLACK_SEND = "RUNBOOK_SLACK_SEND"

DEFAULT_SOURCE = "fixture"
DEFAULT_ENVIRONMENT = "unknown"
DEFAULT_AGENT_OUTPUT_DIR = "ops-package"
DEFAULT_JIRA_ISSUE_TYPE = "Incident"
DEFAULT_SLACK_USERNAME = "runbook-generator"
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
    agent_output_dir: str
    observability_provider: str | None
    observability_base_url: str | None
    observability_query: str | None
    observability_dashboard_url: str | None
    confluence_base_url: str | None
    confluence_space_key: str | None
    confluence_parent_page_id: str | None
    jira_base_url: str | None
    jira_project_key: str | None
    jira_issue_type: str
    wiki_base_url: str | None
    slack_webhook_url: str | None
    slack_channel: str | None
    slack_username: str
    slack_send: bool


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
        agent_output_dir=os.environ.get(
            ENV_AGENT_OUTPUT_DIR,
            DEFAULT_AGENT_OUTPUT_DIR,
        ),
        observability_provider=os.environ.get(ENV_OBSERVABILITY_PROVIDER),
        observability_base_url=os.environ.get(ENV_OBSERVABILITY_BASE_URL),
        observability_query=os.environ.get(ENV_OBSERVABILITY_QUERY),
        observability_dashboard_url=os.environ.get(ENV_OBSERVABILITY_DASHBOARD_URL),
        confluence_base_url=os.environ.get(ENV_CONFLUENCE_BASE_URL),
        confluence_space_key=os.environ.get(ENV_CONFLUENCE_SPACE_KEY),
        confluence_parent_page_id=os.environ.get(ENV_CONFLUENCE_PARENT_PAGE_ID),
        jira_base_url=os.environ.get(ENV_JIRA_BASE_URL),
        jira_project_key=os.environ.get(ENV_JIRA_PROJECT_KEY),
        jira_issue_type=os.environ.get(ENV_JIRA_ISSUE_TYPE, DEFAULT_JIRA_ISSUE_TYPE),
        wiki_base_url=os.environ.get(ENV_WIKI_BASE_URL),
        slack_webhook_url=os.environ.get(ENV_SLACK_WEBHOOK_URL),
        slack_channel=os.environ.get(ENV_SLACK_CHANNEL),
        slack_username=os.environ.get(ENV_SLACK_USERNAME, DEFAULT_SLACK_USERNAME),
        slack_send=_env_bool(ENV_SLACK_SEND),
    )


def _env_bool(name: str) -> bool:
    return os.environ.get(name, "").lower() in {"1", "true", "yes", "on"}
