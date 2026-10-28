# fraud_detection/detectors/GraphNetworkAnalyzer.py
from __future__ import annotations
import logging
from typing import Any, Dict, List, Set
from django.core.cache import cache

logger = logging.getLogger(__name__)

class GraphNetworkAnalyzer:
    """Graph-based fraud ring and cluster analyzer."""

    def __init__(self):
        self._cfg = {
            "ring_size_threshold":   3,
            "cluster_risk_score":    70,
            "ring_risk_score":       90,
            "shared_ip_threshold":   4,
            "shared_device_threshold": 3,
        }

    def analyze(self, data: Dict[str, Any]) -> Dict[str, Any]:
        risk = 0; reasons = []; ring_members = []
        user_id    = data.get("user_id")
        ip         = data.get("ip_address", "")
        device_id  = data.get("device_id", "")
        related    = set(str(u) for u in data.get("related_user_ids", []) if u)

        # 1. IP cluster analysis
        if ip:
            ip_users_key = f"graph:ip:{ip}:users"
            ip_users: Set[str] = cache.get(ip_users_key, set())
            if user_id: ip_users.add(str(user_id))
            cache.set(ip_users_key, ip_users, timeout=86400 * 7)
            if len(ip_users) >= self._cfg["shared_ip_threshold"]:
                risk += 50; reasons.append(f"ip_cluster:{len(ip_users)}_users")
                ring_members = list(ip_users)

        # 2. Device cluster
        if device_id:
            dev_users_key = f"graph:dev:{device_id}:users"
            dev_users: Set[str] = cache.get(dev_users_key, set())
            if user_id: dev_users.add(str(user_id))
            cache.set(dev_users_key, dev_users, timeout=86400 * 7)
            if len(dev_users) >= self._cfg["shared_device_threshold"]:
                risk += 40; reasons.append(f"device_cluster:{len(dev_users)}_users")

        # 3. Direct ring detection (bidirectional connections)
        if user_id:
            user_graph_key = f"graph:user:{user_id}:connections"
            connections: Set[str] = cache.get(user_graph_key, set())
            connections.update(related)
            cache.set(user_graph_key, connections, timeout=86400 * 7)

            # Check if we form a ring (A→B, B→A or A→B→C→A)
            ring_detected = False
            for conn_user in related:
                other_key  = f"graph:user:{conn_user}:connections"
                other_conns: Set[str] = cache.get(other_key, set())
                if str(user_id) in other_conns:
                    ring_detected = True
                    break

            if ring_detected and len(connections) >= self._cfg["ring_size_threshold"]:
                risk = max(risk, self._cfg["ring_risk_score"])
                reasons.append(f"fraud_ring:{len(connections)}_members")
            elif len(connections) >= self._cfg["ring_size_threshold"]:
                risk = max(risk, self._cfg["cluster_risk_score"])
                reasons.append(f"large_network:{len(connections)}_connections")

        risk = min(risk, 100)
        return {
            "risk_score":     risk,
            "is_fraud_ring":  risk >= self._cfg["ring_risk_score"],
            "reasons":        reasons,
            "ring_members":   ring_members[:20],
            "user_id":        user_id,
        }

    def analyze_entity(self, user_id=None, ip=None, device_id=None) -> Dict:
        return self.analyze({"user_id": user_id, "ip_address": ip, "device_id": device_id})

    def detect(self, data: Dict) -> Dict:
        return self.analyze(data)

    def batch_detect(self, entities: List[Dict]) -> List[Dict]:
        return [self.analyze(e) for e in entities]
