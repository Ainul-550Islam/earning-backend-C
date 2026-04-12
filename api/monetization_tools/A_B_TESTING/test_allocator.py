"""A_B_TESTING/test_allocator.py — User-to-variant allocation engine."""
import hashlib
from typing import Optional, Tuple


class TestAllocator:
    """Deterministically assigns users to test variants using hashing."""

    @classmethod
    def assign(cls, test, user) -> Tuple[Optional[str], bool]:
        """
        Returns (variant_name, created).
        Uses SHA-256 for deterministic, sticky assignment.
        """
        from ..models import ABTestAssignment
        existing = ABTestAssignment.objects.filter(test=test, user=user).first()
        if existing:
            return existing.variant_name, False

        if test.status != "running":
            return None, False

        hash_int  = int(hashlib.sha256(f"{test.test_id}{user.id}".encode()).hexdigest(), 16)
        bucket    = hash_int % 100

        if bucket >= (test.traffic_split or 100):
            return None, False

        variants = test.variants or []
        if not variants:
            return None, False

        total_w  = sum(v.get("weight", 0) for v in variants)
        if not total_w:
            return None, False

        threshold  = (bucket / 100) * total_w
        cumulative = 0
        chosen     = variants[-1]["name"]
        for v in variants:
            cumulative += v.get("weight", 0)
            if threshold < cumulative:
                chosen = v["name"]
                break

        assignment, created = ABTestAssignment.objects.get_or_create(
            test=test, user=user, defaults={"variant_name": chosen}
        )
        return assignment.variant_name, created

    @classmethod
    def get_assignment(cls, test_id: int, user) -> Optional[str]:
        from ..models import ABTestAssignment
        obj = ABTestAssignment.objects.filter(test_id=test_id, user=user).first()
        return obj.variant_name if obj else None
