"""
marketplace/cache.py — Cache Helpers (Django cache framework)
"""

from django.core.cache import cache
from .constants import CACHE_PRODUCT_TTL, CACHE_CATEGORY_TTL, CACHE_SELLER_TTL


# ──────────────────────────────────────────────
# Product Cache
# ──────────────────────────────────────────────

def get_cached_product(product_id: int):
    return cache.get(f"marketplace:product:{product_id}")


def set_cached_product(product_id: int, data: dict):
    cache.set(f"marketplace:product:{product_id}", data, timeout=CACHE_PRODUCT_TTL)


def invalidate_product_cache(product_id: int):
    cache.delete(f"marketplace:product:{product_id}")


# ──────────────────────────────────────────────
# Category Cache
# ──────────────────────────────────────────────

def get_cached_category_tree(tenant_id: int):
    return cache.get(f"marketplace:category_tree:{tenant_id}")


def set_cached_category_tree(tenant_id: int, data):
    cache.set(f"marketplace:category_tree:{tenant_id}", data, timeout=CACHE_CATEGORY_TTL)


def invalidate_category_tree(tenant_id: int):
    cache.delete(f"marketplace:category_tree:{tenant_id}")


# ──────────────────────────────────────────────
# Seller Cache
# ──────────────────────────────────────────────

def get_cached_seller(seller_id: int):
    return cache.get(f"marketplace:seller:{seller_id}")


def set_cached_seller(seller_id: int, data: dict):
    cache.set(f"marketplace:seller:{seller_id}", data, timeout=CACHE_SELLER_TTL)


def invalidate_seller_cache(seller_id: int):
    cache.delete(f"marketplace:seller:{seller_id}")


# ──────────────────────────────────────────────
# Generic Helpers
# ──────────────────────────────────────────────

def cache_or_compute(key: str, compute_fn, timeout: int = 300):
    """
    Return from cache if available, otherwise call compute_fn,
    store the result, and return it.
    """
    cached = cache.get(key)
    if cached is not None:
        return cached
    result = compute_fn()
    cache.set(key, result, timeout=timeout)
    return result
