"""
Resource Allocator — Dynamically allocates CPU, memory, and storage resources
"""
import logging
import threading
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ResourceAllocation:
    def __init__(self, resource_id: str, cpu_cores: float, memory_gb: float,
                 disk_gb: float, purpose: str, node_id: str = None):
        self.resource_id = resource_id
        self.cpu_cores = cpu_cores
        self.memory_gb = memory_gb
        self.disk_gb = disk_gb
        self.purpose = purpose
        self.node_id = node_id
        self.allocated_at = datetime.utcnow()
        self.released = False


class ResourceAllocator:
    """
    Tracks and manages resource allocations for DR operations.
    Ensures backup jobs, restore operations, and drills don't
    starve the main application of resources.
    """

    # Default resource budgets for DR operations (% of total)
    DR_RESOURCE_BUDGET = {
        "backup": {"cpu_pct": 20, "memory_pct": 15, "disk_pct": 50},
        "restore": {"cpu_pct": 40, "memory_pct": 30, "disk_pct": 60},
        "replication": {"cpu_pct": 10, "memory_pct": 10, "disk_pct": 5},
        "drill": {"cpu_pct": 30, "memory_pct": 25, "disk_pct": 40},
    }

    def __init__(self, total_cpu_cores: float = 8, total_memory_gb: float = 32,
                 total_disk_gb: float = 1000, config: dict = None):
        self.config = config or {}
        self.total_cpu = total_cpu_cores
        self.total_memory = total_memory_gb
        self.total_disk = total_disk_gb
        self._allocations: Dict[str, ResourceAllocation] = {}
        self._lock = threading.Lock()

    @property
    def used_cpu(self) -> float:
        return sum(a.cpu_cores for a in self._allocations.values() if not a.released)

    @property
    def used_memory(self) -> float:
        return sum(a.memory_gb for a in self._allocations.values() if not a.released)

    @property
    def used_disk(self) -> float:
        return sum(a.disk_gb for a in self._allocations.values() if not a.released)

    def available_resources(self) -> dict:
        return {
            "cpu_cores": round(self.total_cpu - self.used_cpu, 2),
            "memory_gb": round(self.total_memory - self.used_memory, 2),
            "disk_gb": round(self.total_disk - self.used_disk, 2),
        }

    def can_allocate(self, cpu: float, memory: float, disk: float) -> bool:
        avail = self.available_resources()
        return (cpu <= avail["cpu_cores"] and
                memory <= avail["memory_gb"] and
                disk <= avail["disk_gb"])

    def allocate(self, resource_id: str, cpu_cores: float, memory_gb: float,
                 disk_gb: float, purpose: str, node_id: str = None) -> Optional[ResourceAllocation]:
        with self._lock:
            if not self.can_allocate(cpu_cores, memory_gb, disk_gb):
                logger.warning(
                    f"Cannot allocate resources for {purpose}: "
                    f"need CPU={cpu_cores} MEM={memory_gb}GB DISK={disk_gb}GB, "
                    f"available={self.available_resources()}"
                )
                return None
            alloc = ResourceAllocation(
                resource_id=resource_id, cpu_cores=cpu_cores,
                memory_gb=memory_gb, disk_gb=disk_gb,
                purpose=purpose, node_id=node_id
            )
            self._allocations[resource_id] = alloc
            logger.info(
                f"Resources allocated: {resource_id} "
                f"CPU={cpu_cores} MEM={memory_gb}GB DISK={disk_gb}GB "
                f"purpose={purpose}"
            )
            return alloc

    def allocate_for_backup(self, resource_id: str) -> Optional[ResourceAllocation]:
        budget = self.DR_RESOURCE_BUDGET["backup"]
        return self.allocate(
            resource_id=resource_id,
            cpu_cores=self.total_cpu * budget["cpu_pct"] / 100,
            memory_gb=self.total_memory * budget["memory_pct"] / 100,
            disk_gb=self.total_disk * budget["disk_pct"] / 100,
            purpose="backup"
        )

    def allocate_for_restore(self, resource_id: str) -> Optional[ResourceAllocation]:
        budget = self.DR_RESOURCE_BUDGET["restore"]
        return self.allocate(
            resource_id=resource_id,
            cpu_cores=self.total_cpu * budget["cpu_pct"] / 100,
            memory_gb=self.total_memory * budget["memory_pct"] / 100,
            disk_gb=self.total_disk * budget["disk_pct"] / 100,
            purpose="restore"
        )

    def release(self, resource_id: str) -> bool:
        with self._lock:
            alloc = self._allocations.get(resource_id)
            if not alloc:
                return False
            alloc.released = True
            logger.info(f"Resources released: {resource_id}")
            return True

    def get_utilization(self) -> dict:
        return {
            "cpu": {"used": round(self.used_cpu, 2), "total": self.total_cpu,
                    "pct": round(self.used_cpu / self.total_cpu * 100, 1)},
            "memory": {"used": round(self.used_memory, 2), "total": self.total_memory,
                       "pct": round(self.used_memory / self.total_memory * 100, 1)},
            "disk": {"used": round(self.used_disk, 2), "total": self.total_disk,
                     "pct": round(self.used_disk / self.total_disk * 100, 1)},
            "active_allocations": len([a for a in self._allocations.values() if not a.released]),
        }

    def list_allocations(self) -> List[dict]:
        return [
            {"id": a.resource_id, "purpose": a.purpose, "cpu": a.cpu_cores,
             "memory_gb": a.memory_gb, "disk_gb": a.disk_gb,
             "allocated_at": a.allocated_at.isoformat(), "released": a.released}
            for a in self._allocations.values()
        ]
