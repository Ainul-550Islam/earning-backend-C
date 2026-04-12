# api/publisher_tools/a_b_testing/test_allocator.py
"""A/B Test Allocator — Traffic allocation to test variants."""
import hashlib
from typing import Optional
from django.core.cache import cache


def allocate_variant(test, user_identifier: str) -> Optional[object]:
    """User-কে test variant assign করে (consistent hashing)。"""
    if test.status != "running":
        return None
    # Consistent hash — same user always gets same variant
    hash_key = hashlib.md5(f"{test.id}:{user_identifier}".encode()).hexdigest()
    hash_int = int(hash_key[:8], 16) % 100
    cumulative = 0
    variants = list(test.variants.all().order_by("id"))
    for variant in variants:
        cumulative += float(variant.traffic_split)
        if hash_int < cumulative:
            return variant
    return variants[-1] if variants else None


def get_user_variant(test, user_identifier: str) -> Optional[object]:
    """Cache থেকে user-এর assigned variant return করে।"""
    cache_key = f"ab_variant:{test.id}:{user_identifier}"
    variant_id = cache.get(cache_key)
    if variant_id:
        from .test_manager import ABTestVariant
        try:
            return ABTestVariant.objects.get(id=variant_id)
        except ABTestVariant.DoesNotExist:
            pass
    # Allocate fresh
    variant = allocate_variant(test, user_identifier)
    if variant:
        cache.set(cache_key, str(variant.id), 86400)
    return variant


def record_exposure(variant, user_identifier: str) -> None:
    """Test exposure record করে।"""
    cache_key = f"ab_exposure:{variant.test.id}:{user_identifier}"
    if not cache.get(cache_key):
        cache.set(cache_key, True, 86400)


def get_variant_traffic_distribution(test) -> dict:
    """Current traffic distribution per variant।"""
    return {
        v.name: {"split": float(v.traffic_split), "impressions": v.total_impressions}
        for v in test.variants.all()
    }
