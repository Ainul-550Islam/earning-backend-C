"""
Docker Integration — DR operations for Docker containers and volumes
"""
import logging
import subprocess
import json
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class DockerIntegration:
    """
    DR integration for Docker environments:
    - Volume backup/restore
    - Container snapshot
    - Compose stack management during DR
    """

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.socket = config.get("socket", "unix:///var/run/docker.sock")

    def _docker(self, *args, timeout: int = 300) -> dict:
        """Run docker command."""
        cmd = ["docker"] + list(args)
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return {"success": result.returncode == 0,
                    "stdout": result.stdout.strip(), "stderr": result.stderr.strip()}
        except FileNotFoundError:
            return {"success": False, "error": "Docker not installed"}
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Docker command timed out"}

    def backup_volume(self, volume_name: str, dest_path: str) -> dict:
        """Backup a Docker volume to a tar archive."""
        logger.info(f"Docker volume backup: {volume_name} -> {dest_path}")
        result = self._docker(
            "run", "--rm",
            "-v", f"{volume_name}:/data",
            "-v", f"{dest_path}:/backup",
            "alpine",
            "tar", "-czf", "/backup/volume_backup.tar.gz", "-C", "/data", ".",
            timeout=3600
        )
        return {"volume": volume_name, "dest": dest_path, **result}

    def restore_volume(self, volume_name: str, archive_path: str) -> dict:
        """Restore a Docker volume from a tar archive."""
        logger.info(f"Docker volume restore: {archive_path} -> {volume_name}")
        # Create volume if it doesn't exist
        self._docker("volume", "create", volume_name)
        result = self._docker(
            "run", "--rm",
            "-v", f"{volume_name}:/data",
            "-v", f"{archive_path}:/backup/archive.tar.gz:ro",
            "alpine",
            "tar", "-xzf", "/backup/archive.tar.gz", "-C", "/data",
            timeout=3600
        )
        return {"volume": volume_name, "archive": archive_path, **result}

    def list_volumes(self) -> List[dict]:
        result = self._docker("volume", "ls", "--format", "{{json .}}")
        volumes = []
        if result["success"]:
            for line in result["stdout"].splitlines():
                try:
                    volumes.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return volumes

    def stop_container(self, container_id: str, timeout: int = 30) -> bool:
        result = self._docker("stop", "-t", str(timeout), container_id)
        return result["success"]

    def start_container(self, container_id: str) -> bool:
        result = self._docker("start", container_id)
        return result["success"]

    def commit_container(self, container_id: str, image_name: str) -> dict:
        """Create an image from a running container (snapshot)."""
        result = self._docker("commit", container_id, image_name)
        logger.info(f"Container committed: {container_id} -> {image_name}")
        return {"container": container_id, "image": image_name, **result}

    def save_image(self, image_name: str, output_path: str) -> dict:
        """Export Docker image to a tar file."""
        result = self._docker("save", "-o", output_path, image_name)
        return {"image": image_name, "output": output_path, **result}

    def load_image(self, archive_path: str) -> dict:
        """Load Docker image from a tar file."""
        result = self._docker("load", "-i", archive_path)
        return {"archive": archive_path, **result}

    def get_container_stats(self, container_id: str) -> dict:
        result = self._docker("stats", container_id, "--no-stream", "--format", "{{json .}}")
        if result["success"] and result["stdout"]:
            try:
                return json.loads(result["stdout"])
            except json.JSONDecodeError:
                pass
        return {"container": container_id, **result}

    def compose_down(self, compose_file: str, project: str = None) -> dict:
        """Stop docker-compose stack for maintenance."""
        cmd_args = ["compose", "-f", compose_file]
        if project:
            cmd_args += ["-p", project]
        cmd_args.append("down")
        result = self._docker(*cmd_args)
        logger.info(f"Docker Compose down: {compose_file}")
        return result

    def compose_up(self, compose_file: str, project: str = None) -> dict:
        """Start docker-compose stack after DR."""
        cmd_args = ["compose", "-f", compose_file]
        if project:
            cmd_args += ["-p", project]
        cmd_args += ["up", "-d"]
        result = self._docker(*cmd_args, timeout=600)
        logger.info(f"Docker Compose up: {compose_file}")
        return result

    def get_health(self) -> dict:
        result = self._docker("info", "--format", "{{json .}}")
        if result["success"] and result["stdout"]:
            try:
                info = json.loads(result["stdout"])
                return {
                    "healthy": True,
                    "containers_running": info.get("ContainersRunning", 0),
                    "containers_total": info.get("Containers", 0),
                    "images": info.get("Images", 0),
                    "server_version": info.get("ServerVersion", ""),
                }
            except json.JSONDecodeError:
                pass
        return {"healthy": False, "error": result.get("error", "Docker info failed")}
