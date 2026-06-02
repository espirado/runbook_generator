# Runbook Generator

Prototype for generating operational runbooks from live environments.

The long-term goal is broader than Kubernetes: collectors discover resources
from clouds, clusters, serverless platforms, databases, networking, and
observability systems, then normalize them into one environment snapshot that
can be rendered into runbooks.

The first live target is **AWS + EKS**.

## Architecture

```text
Collectors
  AWS CLI: EC2, Lambda, RDS, ELBv2, CloudWatch, EKS
  kubectl: deployments, statefulsets, daemonsets, services, ingress, events
  fixture: offline AWS/EKS-shaped demo data
        ↓
Normalized EnvironmentSnapshot
        ↓
Markdown Runbook Renderer
        ↓
runbook.md + optional snapshot.json
        ↓
Agent/reporting package
  agent_context.json, incident_report.md, jira_issue.json,
  confluence_page.json, wiki_page.md
```

The core model is platform-neutral:

- `compute.cluster`
- `compute.workload`
- `compute.vm`
- `compute.serverless_function`
- `compute.node_group`
- `data.database`
- `network.endpoint`
- `network.ingress`
- `network.load_balancer`
- `observability.alert`
- `observability.event`

That keeps the project ready for GCP, Azure, Borg-like internal platforms,
VM fleets, managed databases, queues, and MCP-backed discovery.

## Quick start

Define the target using variables first. CLI flags can still override any of
these values when needed.

```bash
export RUNBOOK_SOURCE=eks
export RUNBOOK_ENVIRONMENT=replace-me-environment
export RUNBOOK_AWS_ACCOUNT=replace-me-aws-account-id
export RUNBOOK_AWS_REGION=replace-me-aws-region
export RUNBOOK_EKS_CLUSTER=replace-me-eks-cluster-name
export RUNBOOK_K8S_NAMESPACE=replace-me-kubernetes-namespace
export RUNBOOK_SERVICE=replace-me-service-or-workload-name
export RUNBOOK_KUBE_CONTEXT=replace-me-kubectl-context
export RUNBOOK_OUTPUT=runbooks/replace-me-service-or-workload-name.md
export RUNBOOK_SNAPSHOT_OUTPUT=runbooks/replace-me-service-or-workload-name.snapshot.json
export RUNBOOK_AGENT_OUTPUT_DIR=ops-package/replace-me-service-or-workload-name
export RUNBOOK_OBSERVABILITY_PROVIDER=replace-me-observability-provider
export RUNBOOK_OBSERVABILITY_BASE_URL=https://replace-me-observability.example.invalid
export RUNBOOK_OBSERVABILITY_QUERY=replace-me-query
export RUNBOOK_OBSERVABILITY_DASHBOARD_URL=https://replace-me-dashboard.example.invalid
export RUNBOOK_CONFLUENCE_BASE_URL=https://replace-me-confluence.example.invalid
export RUNBOOK_CONFLUENCE_SPACE_KEY=replace-me-space-key
export RUNBOOK_CONFLUENCE_PARENT_PAGE_ID=replace-me-parent-page-id
export RUNBOOK_JIRA_BASE_URL=https://replace-me-jira.example.invalid
export RUNBOOK_JIRA_PROJECT_KEY=replace-me-project-key
export RUNBOOK_JIRA_ISSUE_TYPE=Incident
export RUNBOOK_WIKI_BASE_URL=https://replace-me-wiki.example.invalid
```

Then generate from the configured target:

```bash
PYTHONPATH=src python3 -m runbook_generator.cli generate
```

For local demos without live access, set only the source:

```bash
RUNBOOK_SOURCE=fixture PYTHONPATH=src python3 -m runbook_generator.cli generate
```

## AWS/EKS live discovery

The prototype intentionally uses the local CLIs so it can run wherever AWS and
EKS access already exists.

Required for AWS inventory:

```bash
aws sts get-caller-identity
aws configure get region
```

Required for EKS workload inventory:

```bash
kubectl config current-context
kubectl get deployments --all-namespaces
```

Generate a runbook from AWS and EKS using the exported variables:

```bash
PYTHONPATH=src python3 -m runbook_generator.cli generate
```

Use `--source aws` for account/regional AWS resources without querying
Kubernetes workloads.

You can also load the example variable file:

```bash
cp .env.example .env
# edit .env with live values
set -a; . ./.env; set +a
PYTHONPATH=src python3 -m runbook_generator.cli generate
```

## Agent, incident, and documentation package

Generate a full operations package from the same live AWS/EKS target:

```bash
PYTHONPATH=src python3 -m runbook_generator.cli ops-package
```

The package is written to `RUNBOOK_AGENT_OUTPUT_DIR` and contains:

- `runbook.md` - human-readable operational runbook
- `snapshot.json` - normalized live environment inventory
- `observability_signals.json` - monitoring context from the configured platform
- `incident_report.md` - incident-management/reporting draft
- `agent_context.json` - structured task context for Cursor agents or other agents
- `jira_issue.json` - dry-run Jira create-issue payload
- `confluence_page.json` - dry-run Confluence create-page payload
- `wiki_page.md` - generic Markdown wiki page

The generated payloads are intentionally dry-run artifacts. They are ready for
review, publishing automation, or a Cursor agent, but the prototype does not
create Jira issues or Confluence pages as a side effect.

### Cursor-agent workflow

Use `agent_context.json` as the handoff contract for Cursor agents:

1. Load `agent_context.json`.
2. Read the referenced `snapshot.json`, `runbook.md`, and
   `observability_signals.json`.
3. Follow the `instructions` array to triage, draft incident updates, or prepare
   documentation changes.
4. Require human approval before destructive remediation or external publishing.

This keeps the same generated knowledge useful for both humans and autonomous
agents.

## Development

Run tests:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

Install the CLI locally:

```bash
python3 -m pip install -e .
runbook-generator generate --source fixture
```

## Current scope

Implemented:

- Python CLI
- Platform-neutral snapshot model
- AWS CLI collector skeleton for EC2, Lambda, RDS, ELBv2, CloudWatch, and EKS
- kubectl collector skeleton for EKS workloads and routing
- Agent/reporting package for Cursor-agent handoff, incident drafts, Jira,
  Confluence, and wiki artifacts
- Offline fixture collector
- Deterministic Markdown renderer
- LLM prompt contract for future synthesis

Next:

- Add richer dependency inference from tags, labels, security groups, target
  groups, service selectors, and environment variables.
- Add MCP collectors when Kubernetes/AWS MCP tools are configured.
- Add publisher implementations that post approved Jira/Confluence/wiki payloads.
- Add richer observability adapters for Datadog, Grafana, PagerDuty, and
  Prometheus alert APIs.
- Add LLM-backed synthesis using the normalized snapshot as structured input.
