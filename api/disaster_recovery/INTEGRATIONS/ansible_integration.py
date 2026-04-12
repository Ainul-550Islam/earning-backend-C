"""
Ansible Integration — Configuration management and runbook automation
"""
import logging
import subprocess
import json
import os
import tempfile
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class AnsibleIntegration:
    """
    Integrates Ansible for DR automation:
    - Run playbooks for system configuration
    - Execute DR runbooks
    - Manage inventory during failover
    - Verify post-recovery configuration
    """

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.inventory = config.get("inventory", "/etc/ansible/inventory")
        self.playbook_dir = config.get("playbook_dir", "/opt/ansible/playbooks")
        self.vault_password_file = config.get("vault_password_file", None)
        self.extra_vars = config.get("extra_vars", {})

    def _ansible_playbook(self, playbook: str,
                           inventory: str = None,
                           extra_vars: Dict = None,
                           tags: List[str] = None,
                           limit: str = None,
                           timeout: int = 3600) -> dict:
        """Run an Ansible playbook."""
        cmd = [
            "ansible-playbook",
            playbook,
            "-i", inventory or self.inventory,
        ]
        all_vars = {**self.extra_vars, **(extra_vars or {})}
        if all_vars:
            cmd += ["-e", json.dumps(all_vars)]
        if self.vault_password_file:
            cmd += ["--vault-password-file", self.vault_password_file]
        if tags:
            cmd += ["--tags", ",".join(tags)]
        if limit:
            cmd += ["--limit", limit]
        cmd += ["-v"]  # Verbose output
        env = {**os.environ}
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=timeout, env=env
            )
            success = result.returncode == 0
            logger.info(f"Ansible playbook {'succeeded' if success else 'FAILED'}: {playbook}")
            return {
                "success": success,
                "playbook": playbook,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except FileNotFoundError:
            return {"success": False, "error": "Ansible not installed"}
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"Playbook timed out after {timeout}s"}

    def _ansible_ping(self, inventory: str = None, limit: str = None) -> dict:
        """Verify Ansible connectivity to hosts."""
        cmd = ["ansible", "-i", inventory or self.inventory, "all", "-m", "ping"]
        if limit:
            cmd += ["--limit", limit]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            return {"success": result.returncode == 0,
                    "stdout": result.stdout, "stderr": result.stderr}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def run_dr_failover_playbook(self, primary_host: str,
                                  secondary_host: str,
                                  environment: str = "production") -> dict:
        """Run the DR failover playbook."""
        logger.critical(f"Running DR failover playbook: {primary_host} -> {secondary_host}")
        playbook = os.path.join(self.playbook_dir, "dr_failover.yml")
        return self._ansible_playbook(
            playbook,
            extra_vars={
                "failed_primary": primary_host,
                "new_primary": secondary_host,
                "environment": environment,
                "failover_timestamp": datetime.utcnow().isoformat(),
            },
            timeout=1800
        )

    def run_post_recovery_verification(self, target_hosts: str = "all") -> dict:
        """Run verification checks after DR recovery."""
        playbook = os.path.join(self.playbook_dir, "verify_recovery.yml")
        return self._ansible_playbook(
            playbook,
            limit=target_hosts,
            tags=["verify", "health_check"]
        )

    def configure_replica(self, replica_host: str,
                           primary_host: str,
                           db_password: str = "") -> dict:
        """Configure a database replica via Ansible."""
        playbook = os.path.join(self.playbook_dir, "configure_replica.yml")
        return self._ansible_playbook(
            playbook,
            extra_vars={
                "replica_host": replica_host,
                "primary_host": primary_host,
                "db_password": db_password,
            },
            limit=replica_host
        )

    def update_dns_config(self, hosts_group: str, dns_entries: Dict[str, str]) -> dict:
        """Update DNS/hosts configuration across all servers."""
        playbook = os.path.join(self.playbook_dir, "update_dns.yml")
        return self._ansible_playbook(
            playbook,
            extra_vars={"dns_entries": dns_entries},
            limit=hosts_group
        )

    def create_dynamic_inventory(self, hosts: List[Dict]) -> str:
        """Create a temporary dynamic inventory file."""
        inventory_content = {"all": {"hosts": {}}}
        for host in hosts:
            inventory_content["all"]["hosts"][host["hostname"]] = {
                "ansible_host": host.get("ip", host["hostname"]),
                "ansible_user": host.get("user", "ubuntu"),
                "ansible_ssh_private_key_file": host.get("key_file", "~/.ssh/id_rsa"),
                **host.get("vars", {}),
            }
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, dir="/tmp"
        ) as f:
            json.dump(inventory_content, f, indent=2)
            return f.name

    def run_ad_hoc(self, hosts: str, module: str,
                   args: str = "", timeout: int = 120) -> dict:
        """Run an Ansible ad-hoc command."""
        cmd = [
            "ansible", hosts, "-i", self.inventory,
            "-m", module,
        ]
        if args:
            cmd += ["-a", args]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return {"success": result.returncode == 0,
                    "stdout": result.stdout, "stderr": result.stderr}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def restart_service(self, service: str, hosts: str = "all") -> dict:
        """Restart a service across hosts."""
        return self.run_ad_hoc(
            hosts=hosts,
            module="systemd",
            args=f"name={service} state=restarted"
        )

    def check_connectivity(self) -> dict:
        """Ping all hosts to verify connectivity."""
        result = self._ansible_ping()
        lines = result.get("stdout", "").splitlines()
        successful = sum(1 for l in lines if "SUCCESS" in l)
        failed = sum(1 for l in lines if "FAILED" in l or "UNREACHABLE" in l)
        return {
            "connected_hosts": successful,
            "failed_hosts": failed,
            "total_checked": successful + failed,
            "all_reachable": failed == 0,
            **result
        }
