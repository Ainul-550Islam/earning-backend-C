"""
SEARCH_DISCOVERY/elasticsearch_sync.py — Elasticsearch Product Index Sync
===========================================================================
Indexes Product + ProductAttribute + ProductVariant for fast faceted search.

Index schema per product document:
  {
    "id": 1,
    "tenant_id": 1,
    "name": "Samsung Galaxy A54",
    "slug": "samsung-galaxy-a54",
    "description": "...",
    "category_id": 5,
    "category_name": "Smartphones",
    "category_path": "Electronics > Mobile > Smartphones",
    "seller_id": 3,
    "store_name": "TechHub BD",
    "base_price": 35000.00,
    "sale_price": 32000.00,
    "effective_price": 32000.00,
    "discount_percent": 8.6,
    "status": "active",
    "is_featured": true,
    "average_rating": 4.5,
    "review_count": 128,
    "total_sales": 450,
    "tags": ["samsung", "android", "5g"],
    "attributes": {              ← ProductAttribute list for filtering
      "RAM": "8GB",
      "Storage": "128GB",
      "Display": "6.4 inch",
      "Battery": "5000mAh",
      "Color": "Awesome Violet",
      "OS": "Android 13"
    },
    "variants": [
      {"sku": "SAM-A54-BLK", "color": "Black", "size": "", "in_stock": true, "price": 32000},
    ],
    "in_stock": true,
    "created_at": "2024-01-15T10:00:00Z",
    "updated_at": "2024-03-01T08:30:00Z"
  }

Usage:
  from api.marketplace.SEARCH_DISCOVERY.elasticsearch_sync import ElasticsearchSync
  ElasticsearchSync.index_product(product)
  ElasticsearchSync.delete_product(product_id)
  ElasticsearchSync.bulk_reindex(tenant)
"""
from __future__ import annotations

import json
import logging
from typing import List, Optional

from django.conf import settings

logger = logging.getLogger(__name__)

INDEX_NAME_TEMPLATE = "marketplace_products_{tenant_slug}"
ES_SETTINGS = {
    "number_of_shards": 2,
    "number_of_replicas": 1,
}
ES_MAPPINGS = {
    "properties": {
        "id":              {"type": "integer"},
        "tenant_id":       {"type": "integer"},
        "name":            {"type": "text",    "analyzer": "standard",
                            "fields": {"keyword": {"type": "keyword"}}},
        "slug":            {"type": "keyword"},
        "description":     {"type": "text",    "analyzer": "standard"},
        "category_id":     {"type": "integer"},
        "category_name":   {"type": "keyword"},
        "category_path":   {"type": "text"},
        "seller_id":       {"type": "integer"},
        "store_name":      {"type": "keyword"},
        "base_price":      {"type": "float"},
        "sale_price":      {"type": "float"},
        "effective_price": {"type": "float"},
        "discount_percent":{"type": "float"},
        "status":          {"type": "keyword"},
        "is_featured":     {"type": "boolean"},
        "average_rating":  {"type": "float"},
        "review_count":    {"type": "integer"},
        "total_sales":     {"type": "integer"},
        "tags":            {"type": "keyword"},
        "in_stock":        {"type": "boolean"},
        # Nested attributes for faceted filtering
        "attributes":      {"type": "object",  "dynamic": True},
        "variants":        {
            "type": "nested",
            "properties": {
                "sku":      {"type": "keyword"},
                "color":    {"type": "keyword"},
                "size":     {"type": "keyword"},
                "price":    {"type": "float"},
                "in_stock": {"type": "boolean"},
            }
        },
        "created_at":      {"type": "date"},
        "updated_at":      {"type": "date"},
    }
}


def _get_client():
    """Get Elasticsearch client. Returns None if ES not configured."""
    try:
        from elasticsearch import Elasticsearch
        es_url = getattr(settings, "ELASTICSEARCH_URL", "http://localhost:9200")
        es_kwargs = {
            "hosts": [es_url],
            "retry_on_timeout": True,
            "max_retries": 3,
            "timeout": 10,
        }
        # Authentication
        es_user = getattr(settings, "ELASTICSEARCH_USER", None)
        es_pass = getattr(settings, "ELASTICSEARCH_PASSWORD", None)
        if es_user and es_pass:
            es_kwargs["http_auth"] = (es_user, es_pass)

        return Elasticsearch(**es_kwargs)
    except ImportError:
        logger.warning("[ES] elasticsearch-py not installed. Run: pip install elasticsearch==8.*")
        return None
    except Exception as e:
        logger.error("[ES] Cannot create Elasticsearch client: %s", e)
        return None


def _index_name(tenant) -> str:
    return INDEX_NAME_TEMPLATE.format(tenant_slug=tenant.slug)


class ElasticsearchSync:
    """Full sync manager for Elasticsearch product index."""

    # ── Index management ──────────────────────────────────────────────────────
    @classmethod
    def create_index(cls, tenant) -> bool:
        """Create index with mappings. Idempotent."""
        es = _get_client()
        if not es:
            return False
        idx = _index_name(tenant)
        try:
            if not es.indices.exists(index=idx):
                es.indices.create(
                    index=idx,
                    body={
                        "settings": ES_SETTINGS,
                        "mappings": ES_MAPPINGS,
                    }
                )
                logger.info("[ES] Created index: %s", idx)
            return True
        except Exception as e:
            logger.error("[ES] create_index failed for %s: %s", idx, e)
            return False

    @classmethod
    def delete_index(cls, tenant) -> bool:
        es = _get_client()
        if not es:
            return False
        try:
            es.indices.delete(index=_index_name(tenant), ignore=[400, 404])
            return True
        except Exception as e:
            logger.error("[ES] delete_index failed: %s", e)
            return False

    # ── Document operations ───────────────────────────────────────────────────
    @classmethod
    def index_product(cls, product) -> bool:
        """Index (upsert) a single product."""
        es = _get_client()
        if not es:
            return False
        try:
            doc = cls._build_document(product)
            es.index(
                index=_index_name(product.tenant),
                id=str(product.pk),
                document=doc,
            )
            logger.debug("[ES] Indexed product#%s", product.pk)
            return True
        except Exception as e:
            logger.error("[ES] index_product#%s failed: %s", product.pk, e)
            return False

    @classmethod
    def delete_product(cls, tenant, product_id: int) -> bool:
        """Remove product from index (e.g. banned/deleted)."""
        es = _get_client()
        if not es:
            return False
        try:
            es.delete(index=_index_name(tenant), id=str(product_id), ignore=[404])
            logger.debug("[ES] Deleted product#%s from index", product_id)
            return True
        except Exception as e:
            logger.error("[ES] delete_product#%s failed: %s", product_id, e)
            return False

    # ── Bulk operations ───────────────────────────────────────────────────────
    @classmethod
    def bulk_reindex(cls, tenant, batch_size: int = 200) -> dict:
        """
        Full reindex for a tenant. Rebuilds index from scratch.
        Called by management command or Celery task.
        """
        from api.marketplace.models import Product
        from api.marketplace.enums import ProductStatus

        es = _get_client()
        if not es:
            return {"success": False, "reason": "ES not available"}

        cls.create_index(tenant)

        qs = (
            Product.objects
            .filter(tenant=tenant, status=ProductStatus.ACTIVE)
            .prefetch_related("attributes", "variants__inventory")
            .select_related("category", "seller")
        )

        indexed, failed = 0, 0
        batch = []

        for product in qs.iterator(chunk_size=batch_size):
            doc = cls._build_document(product)
            batch.extend([
                {"index": {"_index": _index_name(tenant), "_id": str(product.pk)}},
                doc,
            ])
            if len(batch) >= batch_size * 2:
                ok, err = cls._bulk_execute(es, batch)
                indexed += ok
                failed  += err
                batch = []

        if batch:
            ok, err = cls._bulk_execute(es, batch)
            indexed += ok
            failed  += err

        result = {"indexed": indexed, "failed": failed, "tenant": tenant.slug}
        logger.info("[ES] Bulk reindex complete: %s", result)
        return result

    @classmethod
    def _bulk_execute(cls, es, actions: list):
        from elasticsearch.helpers import bulk, BulkIndexError
        try:
            success, failed = bulk(es, actions, raise_on_error=False, stats_only=True)
            return success, failed
        except BulkIndexError as e:
            logger.error("[ES] Bulk error: %d failures", len(e.errors))
            return 0, len(e.errors)
        except Exception as e:
            logger.error("[ES] Bulk execute error: %s", e)
            return 0, len(actions) // 2

    # ── Document builder ──────────────────────────────────────────────────────
    @classmethod
    def _build_document(cls, product) -> dict:
        """Build the full ES document for a product including all attributes."""
        # Flatten attributes → dict {"RAM": "8GB", "Color": "Black", ...}
        attrs = {}
        for attr in product.attributes.all():
            value = f"{attr.value} {attr.unit}".strip()
            attrs[attr.name] = value

        # Variants
        variants = []
        for v in product.variants.filter(is_active=True):
            try:
                in_stock = v.inventory.available_quantity > 0 or v.inventory.allow_backorder
                v_price  = float(v.effective_price)
            except Exception:
                in_stock = False
                v_price  = float(product.base_price)

            variants.append({
                "sku":      v.sku,
                "color":    v.color,
                "size":     v.size,
                "price":    v_price,
                "in_stock": in_stock,
            })

        in_stock = any(v["in_stock"] for v in variants) if variants else False

        # Tags
        tags = [t.strip() for t in (product.tags or "").split(",") if t.strip()]

        # Category
        cat_path = product.category.full_path if product.category else ""
        cat_id   = product.category_id
        cat_name = product.category.name if product.category else ""

        return {
            "id":              product.pk,
            "tenant_id":       product.tenant_id,
            "name":            product.name,
            "slug":            product.slug,
            "description":     product.description[:2000],  # truncate for ES
            "short_description": product.short_description,
            "category_id":     cat_id,
            "category_name":   cat_name,
            "category_path":   cat_path,
            "seller_id":       product.seller_id,
            "store_name":      product.seller.store_name if product.seller else "",
            "base_price":      float(product.base_price),
            "sale_price":      float(product.sale_price) if product.sale_price else None,
            "effective_price": float(product.effective_price),
            "discount_percent": float(product.discount_percent),
            "status":          product.status,
            "is_featured":     product.is_featured,
            "average_rating":  float(product.average_rating),
            "review_count":    product.review_count,
            "total_sales":     product.total_sales,
            "tags":            tags,
            "attributes":      attrs,
            "variants":        variants,
            "in_stock":        in_stock,
            "created_at":      product.created_at.isoformat() if product.created_at else None,
            "updated_at":      product.updated_at.isoformat() if product.updated_at else None,
        }


# ── Celery-compatible functions ───────────────────────────────────────────────
def index_product_async(product_id: int, tenant_id: int):
    """Called from Celery task after product save."""
    try:
        from api.marketplace.models import Product
        from api.tenants.models import Tenant
        product = Product.objects.prefetch_related("attributes", "variants__inventory").select_related(
            "category", "seller", "tenant"
        ).get(pk=product_id)
        ElasticsearchSync.index_product(product)
    except Exception as e:
        logger.error("[ES] index_product_async(%s): %s", product_id, e)


def delete_product_async(product_id: int, tenant):
    ElasticsearchSync.delete_product(tenant, product_id)
