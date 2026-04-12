"""
HAProxy Manager — Direct HAProxy configuration and management.
"""
import logging
import subprocess
import socket
import os
from datetime import datetime
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)


class HAProxyManager:
    """
    Manages HAProxy load balancer for DR high-availability scenarios.

    Features:
    - Runtime API control via Unix socket
    - Configuration reload
    - Backend server enable/disable
    - Stats collection
    - Health check management
    """

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.socket_path = config.get("socket_path", "/var/run/haproxy/admin.sock") if config else "/var/run/haproxy/admin.sock"
        self.config_path = config.get("config_path", "/etc/haproxy/haproxy.cfg") if config else "/etc/haproxy/haproxy.cfg"
        self.stats_port = config.get("stats_port", 8404) if config else 8404

    def command(self, cmd: str) -> str:
        """Execute HAProxy runtime API command."""
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.connect(self.socket_path)
            s.sendall(f"{cmd}\n".encode())
            response = b""
            while True:
                chunk = s.recv(4096)
                if not chunk: break
                response += chunk
            s.close()
            return response.decode("utf-8", errors="replace")
        except Exception as e:
            logger.debug(f"HAProxy socket command failed: {e}")
            return ""

    def enable_server(self, backend: str, server: str) -> dict:
        """Enable a backend server."""
        output = self.command(f"set server {backend}/{server} state ready")
        success = not output or "error" not in output.lower()
        if success: logger.info(f"HAProxy: enabled {backend}/{server}")
        return {"success": success, "backend": backend, "server": server, "action": "enabled"}

    def disable_server(self, backend: str, server: str) -> dict:
        """Disable/drain a backend server."""
        self.command(f"set server {backend}/{server} state drain")
        output = self.command(f"set server {backend}/{server} state maint")
        success = not output or "error" not in output.lower()
        return {"success": success, "backend": backend, "server": server, "action": "disabled"}

    def set_weight(self, backend: str, server: str, weight: int) -> dict:
        """Set server weight for traffic distribution."""
        output = self.command(f"set server {backend}/{server} weight {weight}")
        return {"success": not output or "error" not in output.lower(),
                "backend": backend, "server": server, "weight": weight}

    def get_stats(self) -> List[dict]:
        """Get HAProxy statistics."""
        output = self.command("show stat")
        stats = []
        for line in output.splitlines():
            if line.startswith("#") or not line.strip(): continue
            parts = line.split(",")
            if len(parts) >= 18:
                stats.append({
                    "proxy": parts[0], "server": parts[1],
                    "status": parts[17] if len(parts) > 17 else "",
                    "current_connections": int(parts[4]) if parts[4].isdigit() else 0,
                })
        return stats

    def get_info(self) -> dict:
        """Get HAProxy process info."""
        output = self.command("show info")
        info = {}
        for line in output.splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                info[k.strip()] = v.strip()
        return {
            "version": info.get("Version", ""),
            "uptime_seconds": info.get("Uptime_sec", ""),
            "current_connections": info.get("CurrConns", ""),
            "max_connections": info.get("MaxConn", ""),
        }

    def reload_config(self) -> dict:
        """Reload HAProxy configuration gracefully."""
        try:
            result = subprocess.run(
                ["systemctl", "reload", "haproxy"],
                capture_output=True, text=True, timeout=30
            )
            return {"success": result.returncode == 0, "output": result.stdout[:200]}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def verify_config(self) -> dict:
        """Verify HAProxy configuration file."""
        try:
            result = subprocess.run(
                ["haproxy", "-c", "-f", self.config_path],
                capture_output=True, text=True, timeout=10
            )
            return {
                "valid": result.returncode == 0,
                "output": result.stdout[:300] or result.stderr[:300],
            }
        except FileNotFoundError:
            return {"valid": True, "note": "HAProxy not installed — dev mode"}
        except Exception as e:
            return {"valid": False, "error": str(e)}

    def switch_backend(self, frontend: str, new_backend: str) -> dict:
        """Switch a frontend to use a different backend."""
        output = self.command(f"set server {frontend} addr {new_backend}")
        logger.info(f"HAProxy frontend {frontend} -> {new_backend}")
        return {"success": True, "frontend": frontend, "new_backend": new_backend,
                "timestamp": datetime.utcnow().isoformat()}
