"""
api/tasks/search.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Search infrastructure for the task system.
Supports: PostgreSQL full-text search (built-in),
          Elasticsearch (optional), and cache-backed
          simple search for small datasets.

Architecture:
  SearchBackend        — abstract interface
  PostgreSQLBackend    — Django ORM full-text search
  ElasticsearchBackend — Elasticsearch 8.x
  CacheSearchBackend   — Redis-backed fast simple search
  TaskSearchService    — high-level service combining backends
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
from django.db.models import Q, QuerySet
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# SEARCH BACKENDS
# ══════════════════════════════════════════════════════════════════════════════

class SearchBackend:
    """Abstract search backend interface."""

    def index(self, obj: Any) -> bool:
        raise NotImplementedError

    def bulk_index(self, objects: List[Any]) -> int:
        raise NotImplementedError

    def search(self, query: str, **filters) -> List[Dict]:
        raise NotImplementedError

    def delete(self, obj_id: Any, index: str = None) -> bool:
        raise NotImplementedError


class PostgreSQLSearchBackend(SearchBackend):
    """
    Search backend using PostgreSQL full-text search (tsvector).
    Zero external dependencies — works with any PostgreSQL setup.
    """

    def index(self, obj: Any) -> bool:
        """Update search_vector for a single object (if field exists)."""
        try:
            from django.db import connection
            if connection.vendor != 'postgresql':
                return False
            if not hasattr(obj, 'search_vector'):
                return False
            from django.contrib.postgres.search import SearchVector
            model = obj.__class__
            search_fields = getattr(model, 'SEARCH_FIELDS', ['name'])
            model.objects.filter(pk=obj.pk).update(
                search_vector=SearchVector(*search_fields)
            )
            return True
        except Exception as e:
            logger.debug(f"[PG SEARCH] index error: {e}")
            return False

    def bulk_index(self, objects: List[Any]) -> int:
        """Bulk update search vectors."""
        if not objects:
            return 0
        try:
            from django.db import connection
            if connection.vendor != 'postgresql':
                return 0
            from django.contrib.postgres.search import SearchVector
            model        = objects[0].__class__
            search_fields = getattr(model, 'SEARCH_FIELDS', ['name'])
            pks          = [obj.pk for obj in objects]
            model.objects.filter(pk__in=pks).update(
                search_vector=SearchVector(*search_fields)
            )
            return len(pks)
        except Exception as e:
            logger.debug(f"[PG SEARCH] bulk_index error: {e}")
            return 0

    def search_tasks(self, query: str, active_only: bool = True,
                     limit: int = 20) -> QuerySet:
        """Search MasterTask records using PostgreSQL FTS."""
        try:
            from api.tasks.models import MasterTask
            from django.db import connection

            if connection.vendor == 'postgresql':
                from django.contrib.postgres.search import SearchQuery, SearchRank
                search_query = SearchQuery(query)
                qs = MasterTask.objects.annotate(
                    rank=SearchRank('search_vector', search_query)
                )
                if active_only:
                    qs = qs.filter(is_active=True)
                return qs.filter(rank__gt=0).order_by('-rank', '-is_featured')[:limit]
            else:
                # Fallback for non-PostgreSQL (SQLite in tests)
                qs = MasterTask.objects.filter(
                    Q(name__icontains=query) |
                    Q(task_id__icontains=query) |
                    Q(category__icontains=query)
                )
                if active_only:
                    qs = qs.filter(is_active=True)
                return qs[:limit]

        except Exception as e:
            logger.error(f"[PG SEARCH] search_tasks error: {e}")
            return MasterTask.objects.none()

    def search(self, query: str, model_name: str = 'task', **kwargs) -> List[Dict]:
        """Generic search returning list of dicts."""
        try:
            if model_name == 'task':
                qs = self.search_tasks(query, **kwargs)
                return list(qs.values('task_id', 'name', 'category', 'system_type', 'is_active'))
        except Exception as e:
            logger.error(f"[PG SEARCH] search error: {e}")
        return []


class ElasticsearchBackend(SearchBackend):
    """
    Search backend using Elasticsearch 8.x.
    Activated when ELASTICSEARCH_URL is set in settings.
    """

    INDEX_TASKS  = 'tasks-tasks'
    INDEX_OFFERS = 'tasks-offers'
    INDEX_USERS  = 'tasks-users'

    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            from elasticsearch import Elasticsearch
            from django.conf import settings
            es_url = getattr(settings, 'ELASTICSEARCH_URL', None)
            if not es_url:
                return None
            self._client = Elasticsearch(es_url)
            return self._client
        except ImportError:
            logger.debug("[ES] elasticsearch package not installed")
            return None

    def is_available(self) -> bool:
        client = self._get_client()
        if not client:
            return False
        try:
            return client.ping()
        except Exception:
            return False

    def index(self, obj: Any) -> bool:
        """Index a single object into Elasticsearch."""
        client = self._get_client()
        if not client:
            return False
        try:
            doc, index_name = self._obj_to_doc(obj)
            client.index(index=index_name, id=str(obj.pk), document=doc)
            return True
        except Exception as e:
            logger.error(f"[ES] index error: {e}")
            return False

    def bulk_index(self, objects: List[Any]) -> int:
        """Bulk index objects into Elasticsearch."""
        client = self._get_client()
        if not client or not objects:
            return 0
        try:
            from elasticsearch.helpers import bulk
            actions = []
            for obj in objects:
                doc, index_name = self._obj_to_doc(obj)
                actions.append({
                    '_index': index_name,
                    '_id':    str(obj.pk),
                    '_source': doc,
                })
            success, _ = bulk(client, actions, raise_on_error=False)
            return success
        except Exception as e:
            logger.error(f"[ES] bulk_index error: {e}")
            return 0

    def search(self, query: str, index: str = None, filters: dict = None,
               size: int = 20, **kwargs) -> List[Dict]:
        """Search Elasticsearch for matching documents."""
        client = self._get_client()
        if not client:
            return []
        try:
            index_name = index or self.INDEX_TASKS
            body = {
                'query': {
                    'multi_match': {
                        'query':  query,
                        'fields': ['name^3', 'task_id^2', 'category', 'description'],
                        'type':   'best_fields',
                        'fuzziness': 'AUTO',
                    }
                },
                'size': size,
            }
            if filters:
                body['query'] = {
                    'bool': {
                        'must': body['query'],
                        'filter': [{'term': {k: v}} for k, v in filters.items()],
                    }
                }
            resp = client.search(index=index_name, body=body)
            return [
                {'_score': hit['_score'], **hit['_source']}
                for hit in resp['hits']['hits']
            ]
        except Exception as e:
            logger.error(f"[ES] search error: {e}")
            return []

    def delete(self, obj_id: Any, index: str = None) -> bool:
        client = self._get_client()
        if not client:
            return False
        try:
            client.delete(index=index or self.INDEX_TASKS, id=str(obj_id))
            return True
        except Exception as e:
            logger.debug(f"[ES] delete: {e}")
            return False

    def _obj_to_doc(self, obj: Any) -> Tuple[Dict, str]:
        """Convert a model object to an ES document."""
        class_name = obj.__class__.__name__

        if class_name == 'MasterTask':
            return {
                'task_id':     obj.task_id,
                'name':        obj.name,
                'category':    str(obj.category),
                'system_type': str(obj.system_type),
                'is_active':   obj.is_active,
                'is_featured': obj.is_featured,
                'indexed_at':  timezone.now().isoformat(),
            }, self.INDEX_TASKS

        if class_name == 'SmartlinkOffer':
            return {
                'offer_id':   obj.external_id,
                'name':       obj.name,
                'category':   str(obj.category),
                'is_active':  obj.is_active,
                'payout':     str(obj.payout or 0),
                'epc':        str(obj.epc or 0),
                'indexed_at': timezone.now().isoformat(),
            }, self.INDEX_OFFERS

        # Generic fallback
        return {
            'pk':         obj.pk,
            'str':        str(obj),
            'indexed_at': timezone.now().isoformat(),
        }, self.INDEX_TASKS


class CacheSearchBackend(SearchBackend):
    """
    Lightweight search backend using Redis.
    Maintains a simple in-memory index for small datasets.
    Best for: task lists < 10,000 items.
    """

    INDEX_KEY_PREFIX = 'search_idx_'
    INDEX_TTL        = 3600  # 1 hour

    def index(self, obj: Any) -> bool:
        """Add object to cache-based search index."""
        try:
            index_key = f"{self.INDEX_KEY_PREFIX}{obj.__class__.__name__}"
            index     = cache.get(index_key) or {}
            doc       = self._obj_to_tokens(obj)
            index[str(obj.pk)] = doc
            cache.set(index_key, index, timeout=self.INDEX_TTL)
            return True
        except Exception as e:
            logger.debug(f"[CACHE SEARCH] index: {e}")
            return False

    def bulk_index(self, objects: List[Any]) -> int:
        """Bulk index objects."""
        count = 0
        for obj in objects:
            if self.index(obj):
                count += 1
        return count

    def search(self, query: str, model_name: str = 'MasterTask',
               limit: int = 20, **kwargs) -> List[Dict]:
        """Search the cache index by simple token matching."""
        try:
            index_key = f"{self.INDEX_KEY_PREFIX}{model_name}"
            index     = cache.get(index_key) or {}
            query_low = query.lower()
            results   = []

            for pk, doc in index.items():
                searchable = ' '.join(str(v).lower() for v in doc.values())
                if query_low in searchable:
                    results.append({'pk': pk, **doc})
                if len(results) >= limit:
                    break
            return results
        except Exception as e:
            logger.debug(f"[CACHE SEARCH] search: {e}")
            return []

    def delete(self, obj_id: Any, index: str = None) -> bool:
        try:
            index_key = f"{self.INDEX_KEY_PREFIX}{index or 'MasterTask'}"
            idx = cache.get(index_key) or {}
            idx.pop(str(obj_id), None)
            cache.set(index_key, idx, timeout=self.INDEX_TTL)
            return True
        except Exception:
            return False

    def _obj_to_tokens(self, obj: Any) -> Dict:
        """Extract searchable fields from object."""
        tokens = {}
        for field in ['task_id', 'name', 'category', 'system_type',
                      'external_id', 'title', 'description']:
            val = getattr(obj, field, None)
            if val is not None:
                tokens[field] = str(val)
        tokens['pk'] = str(obj.pk)
        return tokens


# ══════════════════════════════════════════════════════════════════════════════
# TASK SEARCH SERVICE
# ══════════════════════════════════════════════════════════════════════════════

class TaskSearchService:
    """
    High-level search service that selects the best available backend.
    Priority: Elasticsearch → PostgreSQL FTS → Cache search
    """

    def __init__(self):
        self._es  = ElasticsearchBackend()
        self._pg  = PostgreSQLSearchBackend()
        self._mem = CacheSearchBackend()

    @property
    def backend(self) -> SearchBackend:
        """Return the best available backend."""
        if self._es.is_available():
            return self._es
        from django.db import connection
        if connection.vendor == 'postgresql':
            return self._pg
        return self._mem

    def search_tasks(self, query: str, active_only: bool = True,
                     limit: int = 20, **filters) -> List[Dict]:
        """
        Search MasterTask records by query string.
        Returns list of dicts with task data.
        """
        if not query or len(query.strip()) < 2:
            return []

        try:
            if isinstance(self.backend, ElasticsearchBackend):
                es_filters = {'is_active': True} if active_only else {}
                es_filters.update(filters)
                return self._es.search(
                    query, index=self._es.INDEX_TASKS,
                    filters=es_filters or None, size=limit
                )
            elif isinstance(self.backend, PostgreSQLSearchBackend):
                qs = self._pg.search_tasks(query, active_only=active_only, limit=limit)
                return list(qs.values('task_id', 'name', 'category',
                                      'system_type', 'is_active', 'is_featured'))
            else:
                return self._mem.search(query, model_name='MasterTask', limit=limit)
        except Exception as e:
            logger.error(f"[SEARCH] search_tasks error: {e}")
            return []

    def search_offers(self, query: str, country: str = None,
                      device: str = None, limit: int = 20) -> List[Dict]:
        """Search SmartlinkOffer records."""
        if not query:
            return []
        try:
            if isinstance(self.backend, ElasticsearchBackend):
                filters = {'is_active': True}
                return self._es.search(
                    query, index=self._es.INDEX_OFFERS,
                    filters=filters, size=limit
                )
            # ORM fallback
            try:
                from ad_networks.models import SmartlinkOffer
                qs = SmartlinkOffer.objects.filter(
                    is_active=True
                ).filter(
                    Q(name__icontains=query) |
                    Q(external_id__icontains=query) |
                    Q(category__icontains=query)
                )
                if country:
                    qs = qs.filter(Q(countries__contains=[country]) | Q(countries__isnull=True))
                if device:
                    qs = qs.filter(Q(device_types__contains=[device]) | Q(device_types__isnull=True))
                return list(qs.values('id', 'external_id', 'name', 'payout',
                                      'epc', 'quality_score')[:limit])
            except ImportError:
                return []
        except Exception as e:
            logger.error(f"[SEARCH] search_offers error: {e}")
            return []

    def index_task(self, task) -> bool:
        """Index a single MasterTask."""
        return self.backend.index(task)

    def rebuild_task_index(self) -> int:
        """Rebuild the entire task search index."""
        try:
            from api.tasks.models import MasterTask
            tasks = list(MasterTask.objects.filter(is_active=True))
            return self.backend.bulk_index(tasks)
        except Exception as e:
            logger.error(f"[SEARCH] rebuild_task_index: {e}")
            return 0

    def rebuild_offer_index(self) -> int:
        """Rebuild the entire offer search index."""
        try:
            from ad_networks.models import SmartlinkOffer
            offers = list(SmartlinkOffer.objects.filter(is_active=True))
            return self.backend.bulk_index(offers)
        except Exception as e:
            logger.error(f"[SEARCH] rebuild_offer_index: {e}")
            return 0

    def autocomplete(self, prefix: str, model: str = 'task',
                     limit: int = 10) -> List[str]:
        """
        Autocomplete suggestions for a prefix string.
        Returns list of matching names.
        """
        if not prefix or len(prefix) < 2:
            return []

        # Check cache first
        cache_key = f'autocomplete_{model}_{prefix.lower()}'
        cached    = cache.get(cache_key)
        if cached is not None:
            return cached

        results = []
        try:
            if model == 'task':
                from api.tasks.models import MasterTask
                qs = MasterTask.objects.filter(
                    is_active=True,
                    name__istartswith=prefix,
                ).values_list('name', flat=True)[:limit]
                results = list(qs)
            elif model == 'offer':
                from ad_networks.models import SmartlinkOffer
                qs = SmartlinkOffer.objects.filter(
                    is_active=True,
                    name__istartswith=prefix,
                ).values_list('name', flat=True)[:limit]
                results = list(qs)
        except ImportError:
            pass
        except Exception as e:
            logger.error(f"[SEARCH] autocomplete error: {e}")

        cache.set(cache_key, results, timeout=300)
        return results

    def get_similar_tasks(self, task_id: str, limit: int = 5) -> List[Dict]:
        """Find tasks similar to a given task_id based on category."""
        try:
            from api.tasks.models import MasterTask
            source = MasterTask.objects.filter(task_id=task_id).first()
            if not source:
                return []
            similar = MasterTask.objects.filter(
                is_active=True,
                category=source.category,
            ).exclude(task_id=task_id).values(
                'task_id', 'name', 'category'
            )[:limit]
            return list(similar)
        except Exception as e:
            logger.error(f"[SEARCH] get_similar_tasks: {e}")
            return []


# ══════════════════════════════════════════════════════════════════════════════
# SINGLETON SERVICE
# ══════════════════════════════════════════════════════════════════════════════

_search_service: Optional[TaskSearchService] = None


def get_search_service() -> TaskSearchService:
    """Return the singleton TaskSearchService instance."""
    global _search_service
    if _search_service is None:
        _search_service = TaskSearchService()
    return _search_service


# ══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def search_tasks(query: str, **kwargs) -> List[Dict]:
    """Search tasks — convenience wrapper."""
    return get_search_service().search_tasks(query, **kwargs)


def search_offers(query: str, **kwargs) -> List[Dict]:
    """Search offers — convenience wrapper."""
    return get_search_service().search_offers(query, **kwargs)


def autocomplete_tasks(prefix: str, limit: int = 10) -> List[str]:
    """Autocomplete task names."""
    return get_search_service().autocomplete(prefix, model='task', limit=limit)


def rebuild_all_indexes() -> Dict[str, int]:
    """Rebuild all search indexes. Returns count per index."""
    svc   = get_search_service()
    tasks  = svc.rebuild_task_index()
    offers = svc.rebuild_offer_index()
    return {'tasks': tasks, 'offers': offers}


__all__ = [
    'SearchBackend', 'PostgreSQLSearchBackend', 'ElasticsearchBackend',
    'CacheSearchBackend', 'TaskSearchService', 'get_search_service',
    'search_tasks', 'search_offers', 'autocomplete_tasks', 'rebuild_all_indexes',
]
