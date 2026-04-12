"""
SEARCH_DISCOVERY/search_engine.py — Unified Search Engine
==========================================================
Routes queries to Elasticsearch (if available) with Django ORM fallback.

Features:
  - Full-text search (name, description, tags)
  - Faceted filters (category, price range, rating, attributes like RAM/Color)
  - Sorting (price, rating, sales, newest)
  - Pagination with cursor support
  - Autocomplete suggestions
  - Spell correction via ES
  - Synonym-aware queries
  - Tenant isolation

Usage:
  engine = SearchEngine(tenant)
  results = engine.search("samsung galaxy", filters={"RAM": "8GB", "min_price": 10000})
  suggestions = engine.autocomplete("sams")
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.db.models import Q, QuerySet
from django.core.cache import cache

logger = logging.getLogger(__name__)

SEARCH_CACHE_TTL = 60   # seconds


# ─────────────────────────────────────────────────────────────────────────────
# Query / Result data structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SearchQuery:
    text: str = ""
    tenant_id: int = 0
    category_id: Optional[int] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    min_rating: Optional[float] = None
    in_stock_only: bool = True
    is_featured: Optional[bool] = None
    seller_id: Optional[int] = None
    # Attribute filters: {"RAM": "8GB", "Color": "Black"}
    attributes: Dict[str, str] = field(default_factory=dict)
    # Sort: "relevance" | "price_asc" | "price_desc" | "rating" | "newest" | "sales"
    sort_by: str = "relevance"
    page: int = 1
    page_size: int = 20


@dataclass
class SearchResult:
    products: List[Any]         # product dicts or ORM instances
    total: int
    page: int
    page_size: int
    num_pages: int
    facets: Dict[str, Any]       # available filter options
    took_ms: float               # query time
    engine: str                  # "elasticsearch" | "django_orm"


# ─────────────────────────────────────────────────────────────────────────────
# Main engine
# ─────────────────────────────────────────────────────────────────────────────

class SearchEngine:

    def __init__(self, tenant):
        self.tenant = tenant
        self._es = None
        self._es_available = None

    def search(self, text: str = "", filters: dict = None, sort_by: str = "relevance",
               page: int = 1, page_size: int = 20) -> SearchResult:
        """
        Main search entry point.
        Tries Elasticsearch first, falls back to Django ORM.
        """
        import time
        filters = filters or {}
        start = time.monotonic()

        query = SearchQuery(
            text=text,
            tenant_id=self.tenant.pk,
            category_id=filters.get("category_id"),
            min_price=filters.get("min_price"),
            max_price=filters.get("max_price"),
            min_rating=filters.get("min_rating"),
            in_stock_only=filters.get("in_stock_only", True),
            is_featured=filters.get("is_featured"),
            seller_id=filters.get("seller_id"),
            attributes={k: v for k, v in filters.items()
                        if k not in {"category_id", "min_price", "max_price",
                                     "min_rating", "in_stock_only", "is_featured", "seller_id"}},
            sort_by=sort_by,
            page=page,
            page_size=page_size,
        )

        # Cache key
        cache_key = self._cache_key(query)
        cached = cache.get(cache_key)
        if cached:
            logger.debug("[Search] Cache hit: %s", cache_key[:60])
            cached.engine += " (cached)"
            return cached

        if self._is_es_available():
            result = self._es_search(query)
        else:
            result = self._orm_search(query)

        result.took_ms = round((time.monotonic() - start) * 1000, 2)
        cache.set(cache_key, result, SEARCH_CACHE_TTL)
        return result

    def autocomplete(self, prefix: str, limit: int = 8) -> List[str]:
        """Return name suggestions for search-as-you-type."""
        if len(prefix) < 2:
            return []

        cache_key = f"autocomplete:{self.tenant.pk}:{prefix.lower()}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        if self._is_es_available():
            suggestions = self._es_autocomplete(prefix, limit)
        else:
            suggestions = self._orm_autocomplete(prefix, limit)

        cache.set(cache_key, suggestions, 120)
        return suggestions

    def similar_products(self, product_id: int, limit: int = 8) -> List[Any]:
        """'More like this' recommendations via ES, ORM fallback."""
        if self._is_es_available():
            return self._es_mlt(product_id, limit)
        return self._orm_similar(product_id, limit)

    # ── Elasticsearch path ────────────────────────────────────────────────────
    def _es_search(self, q: SearchQuery) -> SearchResult:
        from api.marketplace.SEARCH_DISCOVERY.elasticsearch_sync import _index_name, _get_client
        es = _get_client()
        idx = _index_name(self.tenant)

        es_query = self._build_es_query(q)
        es_sort   = self._build_es_sort(q.sort_by)

        from_offset = (q.page - 1) * q.page_size
        try:
            resp = es.search(
                index=idx,
                body={
                    "query":   es_query,
                    "sort":    es_sort,
                    "from":    from_offset,
                    "size":    q.page_size,
                    "aggs":    self._build_aggregations(),
                    "highlight": {
                        "fields": {"name": {}, "description": {}},
                        "pre_tags": ["<mark>"],
                        "post_tags": ["</mark>"],
                    },
                },
            )

            total   = resp["hits"]["total"]["value"]
            hits    = [h["_source"] for h in resp["hits"]["hits"]]
            facets  = self._parse_aggregations(resp.get("aggregations", {}))
            pages   = max(1, -(-total // q.page_size))

            return SearchResult(
                products=hits,
                total=total,
                page=q.page,
                page_size=q.page_size,
                num_pages=pages,
                facets=facets,
                took_ms=0,
                engine="elasticsearch",
            )
        except Exception as e:
            logger.error("[Search][ES] search failed, falling back to ORM: %s", e)
            self._es_available = False
            return self._orm_search(q)

    def _build_es_query(self, q: SearchQuery) -> dict:
        must    = []
        filters = []

        # Tenant isolation
        filters.append({"term": {"tenant_id": q.tenant_id}})
        filters.append({"term": {"status": "active"}})

        # Full-text search
        if q.text:
            must.append({
                "multi_match": {
                    "query": q.text,
                    "fields": ["name^4", "description^1", "tags^2", "category_name^2",
                               "store_name^1", "attributes.*^2"],
                    "type": "best_fields",
                    "fuzziness": "AUTO",
                    "operator": "or",
                }
            })

        # Category filter
        if q.category_id:
            filters.append({"term": {"category_id": q.category_id}})

        # Price range
        price_range = {}
        if q.min_price is not None:
            price_range["gte"] = q.min_price
        if q.max_price is not None:
            price_range["lte"] = q.max_price
        if price_range:
            filters.append({"range": {"effective_price": price_range}})

        # Rating
        if q.min_rating:
            filters.append({"range": {"average_rating": {"gte": q.min_rating}}})

        # In stock
        if q.in_stock_only:
            filters.append({"term": {"in_stock": True}})

        # Featured
        if q.is_featured is not None:
            filters.append({"term": {"is_featured": q.is_featured}})

        # Seller
        if q.seller_id:
            filters.append({"term": {"seller_id": q.seller_id}})

        # Attribute filters (e.g. {"RAM": "8GB"})
        for attr_name, attr_value in q.attributes.items():
            filters.append({"term": {f"attributes.{attr_name}": attr_value}})

        es_query = {
            "bool": {
                "filter": filters,
            }
        }
        if must:
            es_query["bool"]["must"] = must

        return es_query

    def _build_es_sort(self, sort_by: str) -> list:
        sorts = {
            "relevance":  ["_score", {"total_sales": "desc"}],
            "price_asc":  [{"effective_price": "asc"}],
            "price_desc": [{"effective_price": "desc"}],
            "rating":     [{"average_rating": "desc"}, {"review_count": "desc"}],
            "newest":     [{"created_at": "desc"}],
            "sales":      [{"total_sales": "desc"}],
        }
        return sorts.get(sort_by, sorts["relevance"])

    def _build_aggregations(self) -> dict:
        """Aggregations for faceted search sidebar."""
        return {
            "categories": {
                "terms": {"field": "category_name", "size": 20}
            },
            "price_ranges": {
                "range": {
                    "field": "effective_price",
                    "ranges": [
                        {"key": "under_500",    "to": 500},
                        {"key": "500_2000",     "from": 500,  "to": 2000},
                        {"key": "2000_10000",   "from": 2000, "to": 10000},
                        {"key": "10000_50000",  "from": 10000, "to": 50000},
                        {"key": "over_50000",   "from": 50000},
                    ]
                }
            },
            "ratings": {
                "terms": {"field": "average_rating", "size": 5}
            },
            "in_stock": {
                "terms": {"field": "in_stock"}
            },
            # Dynamic attribute aggregations
            "attributes_color":   {"terms": {"field": "attributes.Color",   "size": 20}},
            "attributes_ram":     {"terms": {"field": "attributes.RAM",     "size": 10}},
            "attributes_size":    {"terms": {"field": "attributes.Size",    "size": 15}},
            "attributes_material":{"terms": {"field": "attributes.Material","size": 15}},
        }

    def _parse_aggregations(self, aggs: dict) -> dict:
        """Convert ES aggregation response into clean facet data."""
        def _buckets(key):
            return [
                {"value": b["key"], "count": b["doc_count"]}
                for b in aggs.get(key, {}).get("buckets", [])
            ]

        return {
            "categories":   _buckets("categories"),
            "price_ranges": [
                {"key": b["key"], "count": b["doc_count"]}
                for b in aggs.get("price_ranges", {}).get("buckets", [])
            ],
            "ratings":      _buckets("ratings"),
            "attributes": {
                "Color":    _buckets("attributes_color"),
                "RAM":      _buckets("attributes_ram"),
                "Size":     _buckets("attributes_size"),
                "Material": _buckets("attributes_material"),
            },
        }

    def _es_autocomplete(self, prefix: str, limit: int) -> List[str]:
        from api.marketplace.SEARCH_DISCOVERY.elasticsearch_sync import _index_name, _get_client
        es = _get_client()
        try:
            resp = es.search(
                index=_index_name(self.tenant),
                body={
                    "suggest": {
                        "name_suggest": {
                            "prefix": prefix,
                            "completion": {"field": "name.keyword", "size": limit},
                        }
                    },
                    "query": {
                        "bool": {
                            "must": [{"match_phrase_prefix": {"name": prefix}}],
                            "filter": [
                                {"term": {"tenant_id": self.tenant.pk}},
                                {"term": {"status": "active"}},
                            ],
                        }
                    },
                    "size": limit,
                    "_source": ["name"],
                },
            )
            return [h["_source"]["name"] for h in resp["hits"]["hits"]]
        except Exception as e:
            logger.error("[Search][ES] autocomplete failed: %s", e)
            return self._orm_autocomplete(prefix, limit)

    def _es_mlt(self, product_id: int, limit: int) -> list:
        from api.marketplace.SEARCH_DISCOVERY.elasticsearch_sync import _index_name, _get_client
        es = _get_client()
        try:
            resp = es.search(
                index=_index_name(self.tenant),
                body={
                    "query": {
                        "more_like_this": {
                            "fields": ["name", "description", "tags", "attributes.*"],
                            "like": [{"_id": str(product_id)}],
                            "min_term_freq": 1,
                            "max_query_terms": 12,
                        }
                    },
                    "filter": [{"term": {"status": "active"}}],
                    "size": limit,
                },
            )
            return [h["_source"] for h in resp["hits"]["hits"]]
        except Exception as e:
            logger.error("[Search][ES] MLT failed: %s", e)
            return self._orm_similar(product_id, limit)

    # ── Django ORM fallback ───────────────────────────────────────────────────
    def _orm_search(self, q: SearchQuery) -> SearchResult:
        from api.marketplace.models import Product
        from api.marketplace.enums import ProductStatus

        qs = (
            Product.objects
            .filter(tenant=self.tenant, status=ProductStatus.ACTIVE)
            .select_related("category", "seller")
            .prefetch_related("attributes")
        )

        # Text search
        if q.text:
            qs = qs.filter(
                Q(name__icontains=q.text)
                | Q(description__icontains=q.text)
                | Q(tags__icontains=q.text)
            )

        # Filters
        if q.category_id:
            qs = qs.filter(category_id=q.category_id)
        if q.min_price is not None:
            qs = qs.filter(base_price__gte=q.min_price)
        if q.max_price is not None:
            qs = qs.filter(base_price__lte=q.max_price)
        if q.min_rating:
            qs = qs.filter(average_rating__gte=q.min_rating)
        if q.is_featured is not None:
            qs = qs.filter(is_featured=q.is_featured)
        if q.seller_id:
            qs = qs.filter(seller_id=q.seller_id)

        # Attribute filters
        for attr_name, attr_value in q.attributes.items():
            qs = qs.filter(
                attributes__name=attr_name,
                attributes__value__icontains=attr_value,
            )

        # Sort
        sort_map = {
            "price_asc":  "base_price",
            "price_desc": "-base_price",
            "rating":     "-average_rating",
            "newest":     "-created_at",
            "sales":      "-total_sales",
        }
        qs = qs.order_by(sort_map.get(q.sort_by, "-total_sales"))

        total    = qs.count()
        pages    = max(1, -(-total // q.page_size))
        offset   = (q.page - 1) * q.page_size
        products = list(qs[offset: offset + q.page_size])

        return SearchResult(
            products=products,
            total=total,
            page=q.page,
            page_size=q.page_size,
            num_pages=pages,
            facets=self._orm_facets(q),
            took_ms=0,
            engine="django_orm",
        )

    def _orm_facets(self, q: SearchQuery) -> dict:
        """Build basic facets from ORM for sidebar filters."""
        from api.marketplace.models import Category, ProductAttribute
        from django.db.models import Count, Min, Max

        cats = (
            Category.objects
            .filter(tenant=self.tenant, is_active=True, products__status="active")
            .annotate(count=Count("products"))
            .values("id", "name", "count")
            .order_by("-count")[:20]
        )

        price_agg = (
            __import__("api.marketplace.models", fromlist=["Product"])
            .Product.objects
            .filter(tenant=self.tenant, status="active")
            .aggregate(min_p=Min("base_price"), max_p=Max("base_price"))
        )

        return {
            "categories": list(cats),
            "price_range": {
                "min": float(price_agg["min_p"] or 0),
                "max": float(price_agg["max_p"] or 0),
            },
        }

    def _orm_autocomplete(self, prefix: str, limit: int) -> List[str]:
        from api.marketplace.models import Product
        return list(
            Product.objects.filter(
                tenant=self.tenant, status="active",
                name__istartswith=prefix,
            ).values_list("name", flat=True)[:limit]
        )

    def _orm_similar(self, product_id: int, limit: int) -> list:
        from api.marketplace.models import Product
        try:
            product = Product.objects.get(pk=product_id)
            return list(
                Product.objects.filter(
                    tenant=self.tenant, status="active",
                    category=product.category,
                ).exclude(pk=product_id).order_by("-average_rating")[:limit]
            )
        except Product.DoesNotExist:
            return []

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _is_es_available(self) -> bool:
        if self._es_available is not None:
            return self._es_available
        from api.marketplace.SEARCH_DISCOVERY.elasticsearch_sync import _get_client, _index_name
        es = _get_client()
        if not es:
            self._es_available = False
            return False
        try:
            self._es_available = es.indices.exists(index=_index_name(self.tenant))
        except Exception:
            self._es_available = False
        return self._es_available

    @staticmethod
    def _cache_key(q: SearchQuery) -> str:
        import hashlib, json
        key_data = json.dumps(q.__dict__, sort_keys=True, default=str)
        return "search:" + hashlib.md5(key_data.encode()).hexdigest()
