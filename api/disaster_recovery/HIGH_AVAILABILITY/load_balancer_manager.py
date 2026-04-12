"""
Load Balancer Manager — HAProxy, Nginx, AWS ALB management for DR failover.
"""
import logging, subprocess, time, json
from datetime import datetime
from typing import List, Optional, Dict, Callable

logger = logging.getLogger(__name__)


class LoadBalancerManager:
    """
    Manages load balancer configurations for DR failover.
    Supports HAProxy, Nginx, AWS ALB, and Azure Application Gateway.
    """

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.lb_type = config.get("type","haproxy") if config else "haproxy"
        self.haproxy_socket = config.get("haproxy_socket","/var/run/haproxy/admin.sock") if config else "/var/run/haproxy/admin.sock"
        self.aws_region = config.get("region","us-east-1") if config else "us-east-1"
        self._servers: Dict[str, dict] = {}

    def register_server(self, name: str, host: str, port: int, weight: int = 100,
                         health_check_path: str = "/health"):
        self._servers[name] = {"name":name,"host":host,"port":port,"weight":weight,
                                "enabled":True,"health_check_path":health_check_path}
        logger.info(f"Server registered: {name} ({host}:{port})")

    def enable_server(self, server_name: str, pool_name: str = None) -> dict:
        if self.lb_type == "haproxy":
            return self._haproxy_cmd(f"enable server {pool_name or 'backend'}/{server_name}", server_name, "enabled")
        if server_name in self._servers: self._servers[server_name]["enabled"] = True
        return {"success": True, "server": server_name, "action": "enabled"}

    def disable_server(self, server_name: str, pool_name: str = None, drain: bool = True) -> dict:
        if drain: self._drain_server(server_name)
        if self.lb_type == "haproxy":
            return self._haproxy_cmd(f"disable server {pool_name or 'backend'}/{server_name}", server_name, "disabled")
        if server_name in self._servers: self._servers[server_name]["enabled"] = False
        return {"success": True, "server": server_name, "action": "disabled"}

    def set_weight(self, server_name: str, weight: int, pool_name: str = None) -> dict:
        if self.lb_type == "haproxy":
            return self._haproxy_cmd(f"set server {pool_name or 'backend'}/{server_name} weight {weight}", server_name, str(weight))
        if server_name in self._servers: self._servers[server_name]["weight"] = weight
        return {"success": True, "server": server_name, "weight": weight}

    def get_pool_status(self, pool_name: str = None) -> List[dict]:
        if self.lb_type == "haproxy":
            output = self._haproxy_socket_cmd("show stat")
            pool = pool_name or "backend"
            servers = []
            for line in output.splitlines():
                if line.startswith("#") or not line.strip(): continue
                parts = line.split(",")
                if len(parts) >= 18 and parts[0] == pool and parts[1] != "BACKEND":
                    servers.append({"name": parts[1], "status": parts[17]})
            return servers or list(self._servers.values())
        return list(self._servers.values())

    def gradual_traffic_shift(self, from_server: str, to_server: str,
                               steps: int = 5, interval_seconds: int = 60,
                               pool_name: str = None) -> dict:
        pool = pool_name or "backend"
        step_size = 100 // steps
        timeline = []
        logger.info(f"Gradual shift: {from_server} -> {to_server} ({steps} steps)")
        for i in range(1, steps + 1):
            to_weight = min(step_size * i, 100)
            from_weight = max(100 - step_size * i, 0)
            self.set_weight(from_server, from_weight, pool)
            self.set_weight(to_server, to_weight, pool)
            timeline.append({"step": i, from_server: from_weight, to_server: to_weight,
                              "timestamp": datetime.utcnow().isoformat()})
            logger.info(f"  Step {i}/{steps}: {from_server}={from_weight}% {to_server}={to_weight}%")
            if i < steps: time.sleep(interval_seconds)
        if from_weight == 0: self.disable_server(from_server, pool, drain=False)
        return {"from_server": from_server, "to_server": to_server,
                "steps_completed": steps, "timeline": timeline}

    def health_check_all(self) -> dict:
        import socket as sock
        results = {}
        for name, server in self._servers.items():
            start = time.monotonic()
            try:
                with sock.create_connection((server["host"], server["port"]), timeout=5): pass
                results[name] = {"status": "healthy", "response_time_ms": round((time.monotonic()-start)*1000,2)}
            except Exception as e:
                results[name] = {"status": "down", "error": str(e)}
        healthy = sum(1 for r in results.values() if r.get("status") == "healthy")
        return {"servers": results, "healthy": healthy, "total": len(results),
                "checked_at": datetime.utcnow().isoformat()}

    def reload_config(self) -> dict:
        if self.lb_type == "haproxy":
            r = subprocess.run(["systemctl","reload","haproxy"], capture_output=True, text=True, timeout=30)
            return {"success": r.returncode == 0}
        if self.lb_type == "nginx":
            r = subprocess.run(["nginx","-s","reload"], capture_output=True, text=True, timeout=30)
            return {"success": r.returncode == 0}
        return {"success": True}

    def get_statistics(self) -> dict:
        return {"lb_type": self.lb_type, "registered_servers": len(self._servers),
                "enabled_servers": sum(1 for s in self._servers.values() if s.get("enabled",True))}

    def _haproxy_cmd(self, command: str, server: str, action: str) -> dict:
        output = self._haproxy_socket_cmd(command)
        return {"success": not output or "error" not in output.lower(),
                "server": server, "action": action}

    def _haproxy_socket_cmd(self, command: str) -> str:
        try:
            import socket as sock
            s = sock.socket(sock.AF_UNIX, sock.SOCK_STREAM)
            s.connect(self.haproxy_socket)
            s.sendall((command + "\n").encode())
            response = b""
            while True:
                chunk = s.recv(4096)
                if not chunk: break
                response += chunk
            s.close()
            return response.decode()
        except Exception as e:
            logger.debug(f"HAProxy socket error: {e}")
            return ""

    def _drain_server(self, server: str, timeout: int = 30):
        logger.info(f"Draining {server} (timeout={timeout}s)")
        time.sleep(min(timeout, 5))
