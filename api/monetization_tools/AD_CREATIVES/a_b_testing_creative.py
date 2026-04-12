"""AD_CREATIVES/a_b_testing_creative.py — A/B testing for creatives."""
import hashlib
from typing import List, Optional
from ..models import AdCreative, ABTest


class CreativeABTester:
    """Assigns users to creative variants for A/B testing."""

    @classmethod
    def assign_creative(cls, user_id: str, unit_id: int,
                         test: ABTest) -> Optional[AdCreative]:
        if test.status != "running":
            return None
        variants  = test.variants or []
        if not variants:
            return None
        # Deterministic bucket
        hash_val  = int(hashlib.sha256(f"{test.test_id}{user_id}".encode()).hexdigest(), 16)
        bucket    = hash_val % 100
        cumulative = 0
        for v in variants:
            cumulative += v.get("weight", 0)
            if bucket < cumulative:
                cid = v.get("creative_id")
                if cid:
                    try:
                        return AdCreative.objects.get(pk=cid, status="approved")
                    except AdCreative.DoesNotExist:
                        pass
        return None

    @classmethod
    def get_winner(cls, test: ABTest) -> Optional[str]:
        if test.winner_variant:
            return test.winner_variant
        results = test.results_summary or {}
        if not results:
            return None
        best = max(results.items(), key=lambda x: x[1].get("ctr", 0), default=None)
        return best[0] if best else None
