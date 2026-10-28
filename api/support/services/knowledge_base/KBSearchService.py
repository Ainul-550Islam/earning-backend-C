# api/support/services/knowledge_base/KBSearchService.py  — WORLD #1 COMPLETE
import logging
from django.db.models import Q
from django.core.cache import cache
logger = logging.getLogger(__name__)

class KBSearchService:
    CACHE_TTL = 300

    def search(self, query: str, limit: int = 10, user=None, tenant=None) -> list:
        if not query or len(query.strip()) < 2:
            return []
        query     = query.strip()
        cache_key = f"kb_search:{hash(query)}:{limit}"
        cached    = cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            from api.support.models import KBArticle
            qs = KBArticle.objects.filter(status="published", is_public=True)
            if tenant:
                qs = qs.filter(Q(tenant=tenant) | Q(tenant__isnull=True))

            title_match   = qs.filter(title__icontains=query)
            summary_match = qs.filter(summary__icontains=query).exclude(id__in=title_match)
            body_match    = qs.filter(body__icontains=query).exclude(id__in=title_match).exclude(id__in=summary_match)
            tag_match     = qs.filter(tags__contains=[query.lower()])

            results  = []
            seen_ids = set()

            for article, relevance in [(a, 1.0) for a in list(title_match[:limit])] +                                       [(a, 0.9) for a in list(tag_match[:limit])] +                                       [(a, 0.7) for a in list(summary_match[:limit])] +                                       [(a, 0.5) for a in list(body_match[:limit])]:
                if article.id not in seen_ids and len(results) < limit:
                    results.append(self._format(article, relevance))
                    seen_ids.add(article.id)

            cache.set(cache_key, results, timeout=self.CACHE_TTL)
            return results
        except Exception as e:
            logger.error(f"KB search error: {e}")
            return []

    def search_by_category(self, category_slug: str, limit: int = 10) -> list:
        try:
            from api.support.models import KBArticle
            articles = KBArticle.objects.filter(status="published", is_public=True, category__slug=category_slug).order_by("-view_count")[:limit]
            return [self._format(a) for a in articles]
        except Exception as e:
            logger.error(f"KB category search error: {e}")
            return []

    def get_popular(self, limit: int = 5, tenant=None) -> list:
        try:
            from api.support.models import KBArticle
            qs = KBArticle.objects.filter(status="published", is_public=True)
            if tenant:
                qs = qs.filter(Q(tenant=tenant) | Q(tenant__isnull=True))
            return [self._format(a) for a in qs.order_by("-view_count")[:limit]]
        except Exception as e:
            logger.error(f"KB popular error: {e}")
            return []

    def _format(self, article, relevance: float = 1.0) -> dict:
        return {
            "id":         article.id,
            "title":      article.title,
            "slug":       article.slug,
            "summary":    (article.summary or article.body)[:150],
            "category":   article.category.name if article.category else "",
            "view_count": article.view_count,
            "relevance":  relevance,
            "url":        f"/support/kb/{article.slug}/",
        }

kb_search_service = KBSearchService()