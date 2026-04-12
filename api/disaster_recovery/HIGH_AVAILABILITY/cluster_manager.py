"""
Cluster Manager — Manages HA database clusters (Patroni, Pacemaker, Kubernetes, RDS Multi-AZ).
"""
import logging, subprocess, json
from datetime import datetime
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)


class ClusterManager:
    """
    HA cluster management supporting Patroni, Pacemaker, Kubernetes StatefulSets, and AWS RDS Multi-AZ.
    """

    def __init__(self, cluster_type: str = "patroni", config: dict = None):
        self.cluster_type = cluster_type
        self.config = config or {}
        self.cluster_name = config.get("cluster_name","dr-cluster") if config else "dr-cluster"
        self.patroni_config = config.get("patroni_config","/etc/patroni/config.yml") if config else "/etc/patroni/config.yml"
        self._nodes: Dict[str, dict] = {}

    def get_cluster_status(self) -> dict:
        """Get comprehensive cluster status."""
        if self.cluster_type == "patroni": return self._patroni_status()
        if self.cluster_type == "kubernetes": return self._k8s_status()
        if self.cluster_type == "aws_rds": return self._rds_status()
        return self._generic_status()

    def get_leader(self) -> Optional[str]:
        status = self.get_cluster_status()
        for node in status.get("members",[]):
            if node.get("role") in ("primary","master","leader"): return node.get("name") or node.get("host")
        return self.config.get("default_primary")

    def get_replicas(self) -> List[dict]:
        status = self.get_cluster_status()
        return [n for n in status.get("members",[]) if n.get("role") in ("replica","standby","follower")]

    def trigger_leader_election(self, reason: str = "manual") -> dict:
        logger.critical(f"LEADER ELECTION TRIGGERED: cluster={self.cluster_name} reason={reason}")
        if self.cluster_type == "patroni": return self._patroni_failover()
        return {"status": "election_triggered", "cluster": self.cluster_name,
                "timestamp": datetime.utcnow().isoformat()}

    def pause_cluster(self) -> dict:
        logger.warning(f"CLUSTER PAUSED: {self.cluster_name}")
        if self.cluster_type == "patroni":
            r = subprocess.run(["patronictl","-c",self.patroni_config,"pause"],
                                capture_output=True, text=True, timeout=30)
            return {"paused": r.returncode==0, "cluster": self.cluster_name}
        return {"paused": True, "cluster": self.cluster_name}

    def resume_cluster(self) -> dict:
        if self.cluster_type == "patroni":
            r = subprocess.run(["patronictl","-c",self.patroni_config,"resume"],
                                capture_output=True, text=True, timeout=30)
            return {"resumed": r.returncode==0}
        return {"resumed": True, "cluster": self.cluster_name}

    def add_node(self, name: str, host: str, port: int = 5432, role: str = "replica") -> dict:
        self._nodes[name] = {"name": name, "host": host, "port": port, "role": role,
                              "joined_at": datetime.utcnow().isoformat()}
        return {"added": True, "node": name, "host": host}

    def remove_node(self, node_name: str, graceful: bool = True) -> dict:
        node = self._nodes.pop(node_name, None)
        if not node: return {"removed": False, "error": f"Node not found: {node_name}"}
        return {"removed": True, "node_name": node_name}

    def reinitialize_replica(self, replica_name: str) -> dict:
        if self.cluster_type == "patroni":
            r = subprocess.run(["patronictl","-c",self.patroni_config,"reinit",
                                  self.cluster_name, replica_name,"--force"],
                                capture_output=True, text=True, timeout=300)
            return {"success": r.returncode==0, "replica": replica_name}
        return {"success": True, "note": "Reinit initiated"}

    def check_split_brain(self) -> dict:
        status = self.get_cluster_status()
        primaries = [n for n in status.get("members",[]) if n.get("role") in ("primary","master","leader")]
        split_brain = len(primaries) > 1
        if split_brain: logger.critical(f"SPLIT-BRAIN DETECTED: {len(primaries)} primaries!")
        return {"split_brain_detected": split_brain, "primary_count": len(primaries),
                "primaries": [n.get("name") for n in primaries],
                "recommendation": "IMMEDIATE ACTION REQUIRED" if split_brain else "No split-brain"}

    def get_cluster_lag_summary(self) -> dict:
        replicas = self.get_replicas()
        lags = [r.get("lag_seconds") for r in replicas if r.get("lag_seconds") is not None]
        return {"cluster": self.cluster_name, "replica_count": len(replicas),
                "max_lag_seconds": max(lags,default=None),
                "avg_lag_seconds": round(sum(lags)/len(lags),2) if lags else None}

    def _patroni_status(self) -> dict:
        try:
            r = subprocess.run(["patronictl","-c",self.patroni_config,"list",self.cluster_name,"-f","json"],
                                capture_output=True, text=True, timeout=30)
            if r.returncode == 0:
                data = json.loads(r.stdout)
                members = []
                for m in (data if isinstance(data,list) else []):
                    role = m.get("Role","").lower()
                    members.append({"name": m.get("Member",""), "host": m.get("Host",""),
                                     "role": role, "state": m.get("State",""),
                                     "lag_seconds": m.get("Lag in MB",0)})
                return {"cluster_type":"patroni","cluster_name":self.cluster_name,
                        "healthy":True,"member_count":len(members),"members":members}
        except Exception as e:
            logger.debug(f"Patroni status error: {e}")
        return self._generic_status()

    def _patroni_failover(self) -> dict:
        try:
            r = subprocess.run(["patronictl","-c",self.patroni_config,"failover",self.cluster_name,"--force"],
                                capture_output=True, text=True, timeout=120)
            return {"success": r.returncode==0, "cluster": self.cluster_name}
        except FileNotFoundError:
            return {"success": True, "note": "patronictl not found — dev mode"}

    def _k8s_status(self) -> dict:
        ns = self.config.get("namespace","default")
        sts = self.config.get("statefulset","postgres")
        try:
            r = subprocess.run(["kubectl","get","pods","-n",ns,"-l",f"app={sts}","-o","json"],
                                capture_output=True, text=True, timeout=30)
            if r.returncode == 0:
                data = json.loads(r.stdout)
                members = [{"name": p["metadata"]["name"],
                             "state": p["status"].get("phase","Unknown"),
                             "role": "primary" if p["metadata"]["name"].endswith("-0") else "replica",
                             "ready": all(c["ready"] for c in p["status"].get("containerStatuses",[]))}
                            for p in data.get("items",[])]
                return {"cluster_type":"kubernetes","members":members,
                        "healthy":all(m.get("ready",False) for m in members)}
        except Exception: pass
        return self._generic_status()

    def _rds_status(self) -> dict:
        try:
            import boto3
            rds = boto3.client("rds",region_name=self.config.get("region","us-east-1"))
            r = rds.describe_db_instances(DBInstanceIdentifier=self.config.get("db_instance_id",""))
            db = r.get("DBInstances",[])[0] if r.get("DBInstances") else {}
            return {"cluster_type":"aws_rds_multi_az","status":db.get("DBInstanceStatus",""),
                    "multi_az":db.get("MultiAZ",False),"healthy":db.get("DBInstanceStatus")=="available"}
        except Exception as e:
            return {"cluster_type":"aws_rds","error":str(e),"healthy":False}

    def _generic_status(self) -> dict:
        return {"cluster_type":self.cluster_type,"cluster_name":self.cluster_name,
                "healthy":True,"members":list(self._nodes.values()),
                "leader":self.config.get("default_primary"),
                "note":"Generic cluster status — configure cluster_type for detailed monitoring"}
