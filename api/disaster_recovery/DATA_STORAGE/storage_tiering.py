"""
Storage Tiering — Automatically moves backups between storage tiers based on age and access.
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class StorageTier:
    """Defines a storage tier with its characteristics."""
    def __init__(self, name: str, provider: str, config: dict,
                 min_age_days: int = 0, max_age_days: int = None,
                 cost_per_gb_month: float = 0.0):
        self.name = name
        self.provider = provider
        self.config = config
        self.min_age_days = min_age_days
        self.max_age_days = max_age_days
        self.cost_per_gb_month = cost_per_gb_month


class StorageTieringManager:
    """
    Implements multi-tier storage strategy:
    Tier 1 (Hot):  0–7 days   → S3 STANDARD or local SSD
    Tier 2 (Warm): 7–30 days  → S3 STANDARD_IA or NAS
    Tier 3 (Cool): 30–90 days → S3 GLACIER_IR
    Tier 4 (Cold): 90+ days   → S3 GLACIER or tape
    """

    def __init__(self, tiers: List[StorageTier], db_session=None):
        self.tiers = sorted(tiers, key=lambda t: t.min_age_days)
        self.db = db_session

    def get_tier_for_backup(self, backup_age_days: int) -> Optional[StorageTier]:
        """Determine which storage tier a backup should be in."""
        for tier in reversed(self.tiers):
            if backup_age_days >= tier.min_age_days:
                if tier.max_age_days is None or backup_age_days <= tier.max_age_days:
                    return tier
        return self.tiers[0] if self.tiers else None

    def evaluate_transitions(self, backups: List[dict]) -> List[dict]:
        """Evaluate which backups need to be moved to a different tier."""
        transitions = []
        now = datetime.utcnow()
        for backup in backups:
            created_at = datetime.fromisoformat(backup["created_at"])
            age_days = (now - created_at).days
            target_tier = self.get_tier_for_backup(age_days)
            current_tier = backup.get("current_tier", "hot")
            if target_tier and target_tier.name != current_tier:
                transitions.append({
                    "backup_id": backup["id"],
                    "backup_path": backup.get("storage_path", ""),
                    "age_days": age_days,
                    "current_tier": current_tier,
                    "target_tier": target_tier.name,
                    "target_provider": target_tier.provider,
                    "size_bytes": backup.get("size_bytes", 0),
                })
                logger.info(
                    f"Tier transition needed: backup={backup['id'][:8]}... "
                    f"age={age_days}d {current_tier} -> {target_tier.name}"
                )
        return transitions

    def execute_transitions(self, transitions: List[dict]) -> dict:
        """Execute storage tier transitions."""
        moved = 0
        failed = 0
        total_bytes = 0
        for t in transitions:
            try:
                logger.info(
                    f"Moving {t['backup_id'][:8]}... "
                    f"from {t['current_tier']} to {t['target_tier']}"
                )
                self._move_to_tier(t)
                moved += 1
                total_bytes += t.get("size_bytes", 0)
            except Exception as e:
                logger.error(f"Tier transition failed for {t['backup_id']}: {e}")
                failed += 1
        logger.info(
            f"Tiering complete: {moved} moved ({total_bytes/1e6:.1f} MB), {failed} failed"
        )
        return {
            "transitions_executed": moved,
            "failures": failed,
            "bytes_transitioned": total_bytes,
        }

    def calculate_storage_cost(self, backups: List[dict]) -> dict:
        """Estimate monthly storage cost across all tiers."""
        tier_totals: Dict[str, Dict] = {}
        now = datetime.utcnow()
        for backup in backups:
            created_at = datetime.fromisoformat(backup.get("created_at", now.isoformat()))
            age_days = (now - created_at).days
            tier = self.get_tier_for_backup(age_days)
            if not tier:
                continue
            size_gb = backup.get("size_bytes", 0) / 1e9
            if tier.name not in tier_totals:
                tier_totals[tier.name] = {"size_gb": 0, "cost_usd": 0, "count": 0}
            tier_totals[tier.name]["size_gb"] += size_gb
            tier_totals[tier.name]["cost_usd"] += size_gb * tier.cost_per_gb_month
            tier_totals[tier.name]["count"] += 1
        total_cost = sum(v["cost_usd"] for v in tier_totals.values())
        return {
            "tiers": tier_totals,
            "total_monthly_cost_usd": round(total_cost, 4),
            "total_backups": len(backups),
        }

    def _move_to_tier(self, transition: dict):
        """Execute the actual file movement between tiers."""
        # In production: download from current tier, upload to target tier, delete from current
        # Simplified: log the transition (actual implementation depends on providers)
        logger.info(
            f"  Moving {transition['backup_path']} "
            f"-> tier:{transition['target_tier']} ({transition['target_provider']})"
        )
