"""Kubernetes CLI backed collector for EKS and other Kubernetes clusters."""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any

from runbook_generator.collectors.base import CollectionTarget
from runbook_generator.models import (
    EnvironmentSnapshot,
    OperationalCheck,
    Relationship,
    Resource,
)


class KubectlCollector:
    """Collect Kubernetes workload and routing state using kubectl."""

    name = "kubectl"

    def collect(self, target: CollectionTarget) -> EnvironmentSnapshot:
        cluster = target.cluster or target.kube_context or "current-cluster"
        snapshot = EnvironmentSnapshot(
            name=target.environment,
            providers=["kubernetes"],
            region=target.region,
            metadata={
                "collector": self.name,
                "cluster": cluster,
                "namespace": target.namespace,
                "kube_context": target.kube_context,
            },
        )

        if shutil.which("kubectl") is None:
            snapshot.add_warning(
                "kubectl was not found. Install/configure kubectl to collect EKS workload inventory."
            )
            return snapshot

        deployments = self._collect_workloads(snapshot, target, "deployments")
        statefulsets = self._collect_workloads(snapshot, target, "statefulsets")
        daemonsets = self._collect_workloads(snapshot, target, "daemonsets")
        workloads = {**deployments, **statefulsets, **daemonsets}
        services = self._collect_services(snapshot, target)
        self._collect_ingresses(snapshot, target)
        self._collect_recent_events(snapshot, target)
        self._add_service_relationships(snapshot, services, workloads)
        snapshot.checks.extend(self._kubernetes_checks(target))
        return snapshot

    def _collect_workloads(
        self,
        snapshot: EnvironmentSnapshot,
        target: CollectionTarget,
        resource_type: str,
    ) -> dict[str, dict[str, Any]]:
        data = self._kubectl_json(["get", resource_type], target, snapshot.warnings)
        workloads: dict[str, dict[str, Any]] = {}
        for item in data.get("items", []):
            metadata = item.get("metadata", {})
            spec = item.get("spec", {})
            status = item.get("status", {})
            name = metadata.get("name")
            namespace = metadata.get("namespace", target.namespace or "default")
            if not name or not self._matches_service_scope(name, target):
                continue
            kind = resource_type.rstrip("s")
            resource_id = self._resource_id(target, namespace, f"{kind}/{name}")
            labels = (
                spec.get("template", {})
                .get("metadata", {})
                .get("labels", {})
            )
            workloads[resource_id] = {"labels": labels, "name": name}
            snapshot.add_resource(
                Resource(
                    id=resource_id,
                    name=name,
                    kind="compute.workload",
                    provider="kubernetes",
                    environment=target.environment,
                    region=target.region,
                    status=self._workload_status(status),
                    attributes={
                        "cluster": target.cluster or target.kube_context,
                        "namespace": namespace,
                        "controller": kind,
                        "labels": labels,
                        "replicas": spec.get("replicas"),
                        "ready_replicas": status.get("readyReplicas", 0),
                        "available_replicas": status.get("availableReplicas", 0),
                        "images": self._container_images(spec),
                    },
                )
            )
        return workloads

    def _collect_services(
        self,
        snapshot: EnvironmentSnapshot,
        target: CollectionTarget,
    ) -> dict[str, dict[str, Any]]:
        data = self._kubectl_json(["get", "services"], target, snapshot.warnings)
        services: dict[str, dict[str, Any]] = {}
        for item in data.get("items", []):
            metadata = item.get("metadata", {})
            spec = item.get("spec", {})
            name = metadata.get("name")
            namespace = metadata.get("namespace", target.namespace or "default")
            if not name or not self._matches_service_scope(name, target):
                continue
            resource_id = self._resource_id(target, namespace, f"service/{name}")
            services[resource_id] = {
                "selector": spec.get("selector", {}),
                "namespace": namespace,
            }
            snapshot.add_resource(
                Resource(
                    id=resource_id,
                    name=name,
                    kind="network.endpoint",
                    provider="kubernetes",
                    environment=target.environment,
                    region=target.region,
                    status=spec.get("type"),
                    attributes={
                        "cluster": target.cluster or target.kube_context,
                        "namespace": namespace,
                        "selector": spec.get("selector", {}),
                        "ports": [
                            {
                                "name": port.get("name"),
                                "port": port.get("port"),
                                "target_port": port.get("targetPort"),
                                "protocol": port.get("protocol"),
                            }
                            for port in spec.get("ports", [])
                        ],
                    },
                )
            )
        return services

    def _collect_ingresses(
        self,
        snapshot: EnvironmentSnapshot,
        target: CollectionTarget,
    ) -> None:
        data = self._kubectl_json(["get", "ingresses"], target, snapshot.warnings)
        for item in data.get("items", []):
            metadata = item.get("metadata", {})
            spec = item.get("spec", {})
            name = metadata.get("name")
            namespace = metadata.get("namespace", target.namespace or "default")
            if not name or not self._matches_service_scope(name, target):
                continue
            snapshot.add_resource(
                Resource(
                    id=self._resource_id(target, namespace, f"ingress/{name}"),
                    name=name,
                    kind="network.ingress",
                    provider="kubernetes",
                    environment=target.environment,
                    region=target.region,
                    status="configured",
                    attributes={
                        "cluster": target.cluster or target.kube_context,
                        "namespace": namespace,
                        "hosts": [
                            rule.get("host")
                            for rule in spec.get("rules", [])
                            if rule.get("host")
                        ],
                        "class": spec.get("ingressClassName"),
                    },
                )
            )

    def _collect_recent_events(
        self,
        snapshot: EnvironmentSnapshot,
        target: CollectionTarget,
    ) -> None:
        data = self._kubectl_json(["get", "events"], target, snapshot.warnings)
        for item in data.get("items", [])[-20:]:
            metadata = item.get("metadata", {})
            involved = item.get("involvedObject", {})
            name = metadata.get("name") or involved.get("name")
            namespace = metadata.get("namespace", target.namespace or "default")
            if not name:
                continue
            snapshot.add_resource(
                Resource(
                    id=self._resource_id(target, namespace, f"event/{metadata.get('uid', name)}"),
                    name=name,
                    kind="observability.event",
                    provider="kubernetes",
                    environment=target.environment,
                    region=target.region,
                    status=item.get("type"),
                    attributes={
                        "cluster": target.cluster or target.kube_context,
                        "namespace": namespace,
                        "reason": item.get("reason"),
                        "message": item.get("message"),
                        "involved_kind": involved.get("kind"),
                        "involved_name": involved.get("name"),
                        "last_timestamp": item.get("lastTimestamp")
                        or item.get("eventTime"),
                    },
                )
            )

    def _add_service_relationships(
        self,
        snapshot: EnvironmentSnapshot,
        services: dict[str, dict[str, Any]],
        workloads: dict[str, dict[str, Any]],
    ) -> None:
        for service_id, service in services.items():
            selector = service.get("selector") or {}
            if not selector:
                continue
            for workload_id, workload in workloads.items():
                labels = workload.get("labels") or {}
                if all(labels.get(key) == value for key, value in selector.items()):
                    snapshot.relationships.append(
                        Relationship(
                            source_id=service_id,
                            target_id=workload_id,
                            relationship_type="routes_to",
                            description="Kubernetes Service selector matches workload labels.",
                        )
                    )

    def _kubernetes_checks(self, target: CollectionTarget) -> list[OperationalCheck]:
        namespace_flag = f" -n {target.namespace}" if target.namespace else " --all-namespaces"
        context_flag = f" --context {target.kube_context}" if target.kube_context else ""
        service = target.service or "<deployment>"
        return [
            OperationalCheck(
                title="Check workload rollout",
                command=f"kubectl{context_flag} rollout status deployment/{service}{namespace_flag}",
                description="Confirms the selected workload has completed rollout.",
            ),
            OperationalCheck(
                title="Inspect warning events",
                command=(
                    f"kubectl{context_flag} get events{namespace_flag} "
                    "--field-selector type=Warning --sort-by=.lastTimestamp"
                ),
                description="Identifies scheduling, image pull, and probe failures.",
            ),
            OperationalCheck(
                title="Fetch workload logs",
                command=f"kubectl{context_flag} logs deployment/{service}{namespace_flag} --tail=200",
                description="Starts debugging from the latest application logs.",
            ),
        ]

    def _kubectl_json(
        self,
        args: list[str],
        target: CollectionTarget,
        warnings: list[str],
    ) -> dict[str, Any]:
        command = ["kubectl"]
        if target.kube_context:
            command.extend(["--context", target.kube_context])
        command.extend(args)
        if target.namespace:
            command.extend(["-n", target.namespace])
        else:
            command.append("--all-namespaces")
        command.extend(["-o", "json"])

        try:
            result = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            warnings.append("kubectl command was not found.")
            return {"items": []}
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            warnings.append(
                f"Command failed: {' '.join(command)}"
                + (f" ({stderr})" if stderr else "")
            )
            return {"items": []}

        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            warnings.append(f"kubectl returned non-JSON output: {exc}")
            return {"items": []}

    def _resource_id(self, target: CollectionTarget, namespace: str, path: str) -> str:
        cluster = target.cluster or target.kube_context or "current-cluster"
        return f"k8s:{cluster}:{namespace}:{path}"

    @staticmethod
    def _matches_service_scope(name: str, target: CollectionTarget) -> bool:
        return target.service is None or name == target.service

    @staticmethod
    def _workload_status(status: dict[str, Any]) -> str:
        replicas = status.get("replicas") or 0
        ready = status.get("readyReplicas") or 0
        if replicas == ready and replicas > 0:
            return "Available"
        if replicas == 0:
            return "ScaledToZero"
        return "Degraded"

    @staticmethod
    def _container_images(spec: dict[str, Any]) -> list[str]:
        containers = (
            spec.get("template", {})
            .get("spec", {})
            .get("containers", [])
        )
        return [
            container.get("image")
            for container in containers
            if container.get("image")
        ]
