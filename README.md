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

Run the offline fixture path:

```bash
PYTHONPATH=src python3 -m runbook_generator.cli generate \
  --source fixture \
  --environment production \
  --cluster payments-prod \
  --namespace payments \
  --service checkout-api \
  --output runbooks/checkout-api.md \
  --snapshot-output runbooks/checkout-api.snapshot.json
```

Print to stdout instead:

```bash
PYTHONPATH=src python3 -m runbook_generator.cli generate --source fixture
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

Generate a runbook from AWS and EKS:

```bash
PYTHONPATH=src python3 -m runbook_generator.cli generate \
  --source eks \
  --environment production \
  --region us-east-1 \
  --cluster your-eks-cluster \
  --namespace your-namespace \
  --service your-deployment \
  --kube-context your-kube-context \
  --output runbooks/your-service.md \
  --snapshot-output runbooks/your-service.snapshot.json
```

Use `--source aws` for account/regional AWS resources without querying
Kubernetes workloads.

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
