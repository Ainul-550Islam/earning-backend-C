# api/support/services/knowledge_base/KBRecommendService.py  — WORLD #1 COMPLETE
import logging
from django.core.cache import cache
logger = logging.getLogger(__name__)

CATEGORY_KEYWORDS = {
    "payment":    ["payment","bkash","nagad","transaction","billing"],
    "withdrawal": ["withdrawal","cashout","payout","redeem"],
    "coins":      ["coins","credits","points","reward","balance"],
    "account":    ["account","login","password","suspended","banned"],
    "fraud":      ["fraud","hack","unauthorized","scam","security"],
    "kyc":        ["kyc","verification","identity","document","nid"],
    "technical":  ["error","bug","not working","broken","crash"],
    "referral":   ["referral","invite","commission","affiliate"],
    "offer":      ["offer","task","survey","complete","install"],
}

class KBRecommendService:
    CACHE_TTL = 600

    def suggest_for_ticket(self, subject: str, category: str = "other", limit: int = 3) -> list:
        from api.support.services.knowledge_base.KBSearchService import kb_search_service
        cache_key = f"kb_suggest:{hash(subject)}:{category}:{limit}"
        cached    = cache.get(cache_key)
        if cached is not None:
            return cached
        keywords = CATEGORY_KEYWORDS.get(category, [])
        query    = subject.strip()
        if keywords and keywords[0].lower() not in query.lower():
            query = f"{keywords[0]} {query}"
        results = kb_search_service.search(query, limit=limit)
        if not results and keywords:
            results = kb_search_service.search(" ".join(keywords[:3]), limit=limit)
        cache.set(cache_key, results, timeout=self.CACHE_TTL)
        return results

    def suggest_related(self, article_id: str, limit: int = 3) -> list:
        try:
            from api.support.models import KBArticle
            article = KBArticle.objects.get(id=article_id)
            related = KBArticle.objects.filter(status="published", is_public=True, category=article.category).exclude(id=article.id).order_by("-view_count")[:limit]
            return [{"id":a.id,"title":a.title,"slug":a.slug,"url":f"/support/kb/{a.slug}/"} for a in related]
        except Exception as e:
            logger.error(f"KB related suggest error: {e}")
            return []

    def suggest_for_query(self, query: str, limit: int = 5) -> list:
        from api.support.services.knowledge_base.KBSearchService import kb_search_service
        return kb_search_service.search(query, limit=limit)

kb_recommend_service = KBRecommendService()