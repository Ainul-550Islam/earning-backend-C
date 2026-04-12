"""
Kubernetes Integration — DR operations for Kubernetes workloads
"""
import logging
import json
import subprocess
from datetime import datetime
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)


class KubernetesIntegration:
    """
    Integrates DR operations with Kubernetes:
    - Backup PVCs (Persistent Volume Claims)
    - Scale deployments during DR
    - Manage pod disruption budgets
    - Trigger Velero backups
    """

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.namespace = config.get("namespace", "default")
        self.kubeconfig = config.get("kubeconfig", None)
        self._client = None

    def _get_client(self):
        if not self._client:
            from kubernetes import client, config as k8s_config
            if self.kubeconfig:
                k8s_config.load_kube_config(self.kubeconfig)
            else:
                try:
                    k8s_config.load_incluster_config()
                except Exception:
                    k8s_config.load_kube_config()
            self._client = client
        return self._client

    def _kubectl(self, *args, timeout: int = 60) -> dict:
        """Run kubectl command and return parsed output."""
        cmd = ["kubectl"]
        if self.kubeconfig:
            cmd += ["--kubeconfig", self.kubeconfig]
        cmd += list(args)
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return {"success": result.returncode == 0,
                    "stdout": result.stdout, "stderr": result.stderr}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Velero Backup ──────────────────────────────────────────────────────────

    def trigger_velero_backup(self, backup_name: str = None,
                               namespaces: List[str] = None,
                               include_cluster_resources: bool = True) -> dict:
        """Trigger a Velero backup for specified namespaces."""
        if not backup_name:
            backup_name = f"dr-backup-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
        ns_str = ",".join(namespaces) if namespaces else "*"
        cmd_args = [
            "velero", "backup", "create", backup_name,
            f"--include-namespaces={ns_str}",
        ]
        if include_cluster_resources:
            cmd_args.append("--include-cluster-resources=true")
        result = self._kubectl(*cmd_args)
        logger.info(f"Velero backup triggered: {backup_name}")
        return {"backup_name": backup_name, "namespaces": ns_str, **result}

    def get_velero_backup_status(self, backup_name: str) -> dict:
        result = self._kubectl("velero", "backup", "describe", backup_name, "--json")
        if result["success"] and result["stdout"]:
            try:
                data = json.loads(result["stdout"])
                return {
                    "name": backup_name,
                    "phase": data.get("status", {}).get("phase", "Unknown"),
                    "start_time": data.get("status", {}).get("startTimestamp"),
                    "completion_time": data.get("status", {}).get("completionTimestamp"),
                    "warnings": data.get("status", {}).get("warnings", 0),
                    "errors": data.get("status", {}).get("errors", 0),
                }
            except json.JSONDecodeError:
                pass
        return {"name": backup_name, "phase": "Unknown", **result}

    def trigger_velero_restore(self, backup_name: str,
                                restore_name: str = None,
                                namespaces: List[str] = None) -> dict:
        if not restore_name:
            restore_name = f"restore-{backup_name}-{datetime.utcnow().strftime('%H%M%S')}"
        cmd_args = ["velero", "restore", "create", restore_name,
                    f"--from-backup={backup_name}"]
        if namespaces:
            cmd_args.append(f"--include-namespaces={','.join(namespaces)}")
        result = self._kubectl(*cmd_args)
        logger.info(f"Velero restore triggered: {restore_name} from {backup_name}")
        return {"restore_name": restore_name, "backup_name": backup_name, **result}

    # ── Deployment management ─────────────────────────────────────────────────

    def scale_deployment(self, name: str, replicas: int,
                          namespace: str = None) -> dict:
        ns = namespace or self.namespace
        result = self._kubectl("scale", "deployment", name,
                               f"--replicas={replicas}", f"-n={ns}")
        logger.info(f"K8s scale: {name} -> {replicas} replicas")
        return {"deployment": name, "replicas": replicas, "namespace": ns, **result}

    def scale_all_deployments(self, replicas: int,
                               namespace: str = None,
                               exclude: List[str] = None) -> List[dict]:
        ns = namespace or self.namespace
        result = self._kubectl("get", "deployments", f"-n={ns}",
                               "-o=jsonpath={.items[*].metadata.name}")
        if not result["success"]:
            return []
        deployment_names = result["stdout"].split()
        results = []
        for name in deployment_names:
            if exclude and name in exclude:
                continue
            scale_result = self.scale_deployment(name, replicas, ns)
            results.append(scale_result)
        return results

    def get_deployment_status(self, name: str, namespace: str = None) -> dict:
        ns = namespace or self.namespace
        result = self._kubectl("get", "deployment", name, f"-n={ns}", "-o=json")
        if result["success"] and result["stdout"]:
            try:
                data = json.loads(result["stdout"])
                spec = data.get("spec", {})
                status = data.get("status", {})
                return {
                    "name": name,
                    "desired_replicas": spec.get("replicas", 0),
                    "ready_replicas": status.get("readyReplicas", 0),
                    "available_replicas": status.get("availableReplicas", 0),
                    "updated_replicas": status.get("updatedReplicas", 0),
                    "conditions": status.get("conditions", []),
                }
            except json.JSONDecodeError:
                pass
        return {"name": name, **result}

    # ── PVC Backup ────────────────────────────────────────────────────────────

    def list_pvcs(self, namespace: str = None) -> List[dict]:
        ns = namespace or self.namespace
        result = self._kubectl("get", "pvc", f"-n={ns}", "-o=json")
        pvcs = []
        if result["success"] and result["stdout"]:
            try:
                data = json.loads(result["stdout"])
                for item in data.get("items", []):
                    pvcs.append({
                        "name": item["metadata"]["name"],
                        "namespace": ns,
                        "capacity": item["spec"].get("resources", {}).get("requests", {}).get("storage"),
                        "status": item["status"].get("phase"),
                        "volume_name": item["spec"].get("volumeName"),
                        "storage_class": item["spec"].get("storageClassName"),
                    })
            except json.JSONDecodeError:
                pass
        return pvcs

    def snapshot_pvc(self, pvc_name: str, snapshot_name: str = None,
                      namespace: str = None) -> dict:
        ns = namespace or self.namespace
        if not snapshot_name:
            snapshot_name = f"snap-{pvc_name}-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
        snapshot_yaml = {
            "apiVersion": "snapshot.storage.k8s.io/v1",
            "kind": "VolumeSnapshot",
            "metadata": {"name": snapshot_name, "namespace": ns},
            "spec": {"source": {"persistentVolumeClaimName": pvc_name}}
        }
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            import yaml
            yaml.dump(snapshot_yaml, f)
            tmp_path = f.name
        result = self._kubectl("apply", "-f", tmp_path)
        os.unlink(tmp_path)
        logger.info(f"PVC snapshot created: {snapshot_name} from {pvc_name}")
        return {"pvc": pvc_name, "snapshot": snapshot_name, "namespace": ns, **result}

    # ── Health ────────────────────────────────────────────────────────────────

    def get_cluster_health(self) -> dict:
        node_result = self._kubectl("get", "nodes", "-o=json")
        nodes = []
        if node_result["success"] and node_result["stdout"]:
            try:
                data = json.loads(node_result["stdout"])
                for n in data.get("items", []):
                    conditions = n.get("status", {}).get("conditions", [])
                    ready = any(c["type"] == "Ready" and c["status"] == "True"
                                for c in conditions)
                    nodes.append({
                        "name": n["metadata"]["name"],
                        "ready": ready,
                        "roles": [k.split("/")[1] for k in n["metadata"].get("labels", {})
                                  if k.startswith("node-role.kubernetes.io/")],
                    })
            except json.JSONDecodeError:
                pass
        healthy_nodes = sum(1 for n in nodes if n["ready"])
        return {
            "total_nodes": len(nodes),
            "healthy_nodes": healthy_nodes,
            "is_healthy": healthy_nodes > 0,
            "nodes": nodes,
        }

    def get_namespace_resources(self, namespace: str = None) -> dict:
        ns = namespace or self.namespace
        result = self._kubectl("get", "all", f"-n={ns}", "-o=json")
        if not result["success"]:
            return {"error": result.get("stderr", "kubectl failed")}
        try:
            data = json.loads(result["stdout"])
            kinds = {}
            for item in data.get("items", []):
                kind = item.get("kind", "Unknown")
                kinds[kind] = kinds.get(kind, 0) + 1
            return {"namespace": ns, "resources": kinds}
        except json.JSONDecodeError:
            return {"namespace": ns, "error": "Failed to parse kubectl output"}
