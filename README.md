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
- Offline fixture collector
- Deterministic Markdown renderer
- LLM prompt contract for future synthesis

Next:

- Add richer dependency inference from tags, labels, security groups, target
  groups, service selectors, and environment variables.
- Add MCP collectors when Kubernetes/AWS MCP tools are configured.
- Add LLM-backed synthesis using the normalized snapshot as structured input.
