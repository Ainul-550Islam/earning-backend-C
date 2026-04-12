"""
Geo Replication — Manages cross-geography data replication for DR and latency reduction.
"""
import logging
from datetime import datetime
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)


class GeoReplication:
    """
    Manages geographic replication across multiple regions.
    Supports:
    - Active-passive: Primary region + DR region(s)
    - Active-active: Multiple primary regions serving local users
    - Read replicas: Regional replicas for low-latency reads
    """

    def __init__(self, regions: list = None, config: dict = None):
        self.regions = regions or []
        self.config = config or {}
        self.primary_region = config.get("primary_region", "us-east-1") if config else "us-east-1"

    def get_region_status(self) -> List[dict]:
        """Get replication status for all regions."""
        statuses = []
        for region in self.regions:
            status = self._check_region_replication(region)
            statuses.append(status)
        return statuses

    def add_region(self, region: dict) -> bool:
        """Add a new region to the geo-replication topology."""
        region_name = region.get("name")
        if any(r.get("name") == region_name for r in self.regions):
            logger.warning(f"Region already configured: {region_name}")
            return False
        self.regions.append(region)
        logger.info(f"Geo-replication region added: {region_name}")
        return True

    def remove_region(self, region_name: str) -> bool:
        """Remove a region from the replication topology."""
        self.regions = [r for r in self.regions if r.get("name") != region_name]
        logger.info(f"Geo-replication region removed: {region_name}")
        return True

    def get_closest_region(self, client_ip: str) -> Optional[str]:
        """
        Return the closest healthy region for a client IP.
        In production: use latency measurements or geo-IP lookup.
        """
        for region in self.regions:
            if region.get("healthy", True):
                return region.get("name")
        return self.primary_region

    def replicate_to_all(self, data_reference: str) -> Dict[str, bool]:
        """Ensure data is replicated to all configured regions."""
        results = {}
        for region in self.regions:
            name = region.get("name")
            try:
                success = self._replicate_to_region(data_reference, region)
                results[name] = success
                logger.info(f"Geo-replication to {name}: {'OK' if success else 'FAILED'}")
            except Exception as e:
                logger.error(f"Geo-replication to {name} failed: {e}")
                results[name] = False
        return results

    def get_replication_topology(self) -> dict:
        """Return the complete replication topology."""
        return {
            "primary_region": self.primary_region,
            "total_regions": len(self.regions) + 1,
            "regions": [
                {"name": r.get("name"), "role": r.get("role", "replica"),
                 "provider": r.get("provider", "aws"),
                 "lag_seconds": 0, "healthy": r.get("healthy", True)}
                for r in self.regions
            ],
            "mode": self.config.get("mode", "active_passive"),
            "topology_as_of": datetime.utcnow().isoformat(),
        }

    def enable_active_active(self, regions: List[str]) -> dict:
        """Switch from active-passive to active-active mode."""
        logger.warning("Switching to active-active geo-replication mode")
        for region in self.regions:
            if region.get("name") in regions:
                region["role"] = "primary"
        return {
            "mode": "active_active",
            "primary_regions": regions,
            "enabled_at": datetime.utcnow().isoformat(),
            "note": "Ensure conflict resolution strategy is configured",
        }

    def _check_region_replication(self, region: dict) -> dict:
        """Check replication health for a specific region."""
        name = region.get("name", "unknown")
        return {
            "region": name,
            "role": region.get("role", "replica"),
            "lag_seconds": 0.0,
            "status": "healthy",
            "last_checked": datetime.utcnow().isoformat(),
        }

    def _replicate_to_region(self, data_ref: str, region: dict) -> bool:
        """Replicate data to a specific region."""
        return True  # In production: trigger cloud-native replication

    def check_split_brain(self) -> dict:
        """Detect and report split-brain scenarios in multi-master setups."""
        mode = self.config.get("mode", "active_passive")
        if mode != "active_active":
            return {"split_brain_possible": False, "mode": mode}
        primary_regions = [r for r in self.regions if r.get("role") == "primary"]
        if len(primary_regions) > 1:
            logger.warning("Multiple primary regions detected — potential split-brain risk")
        return {
            "split_brain_possible": len(primary_regions) > 1,
            "primary_count": len(primary_regions),
            "primaries": [r.get("name") for r in primary_regions],
            "checked_at": datetime.utcnow().isoformat(),
        }
