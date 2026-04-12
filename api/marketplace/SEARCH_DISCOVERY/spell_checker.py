"""
SEARCH_DISCOVERY/spell_checker.py — Search Query Spell Correction
"""
import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)


def correct_query(query: str, tenant) -> str:
    """Attempt spell correction using ES suggest or simple dictionary."""
    if not query or len(query) < 3:
        return query

    # Try ES did-you-mean
    try:
        from api.marketplace.SEARCH_DISCOVERY.elasticsearch_sync import _get_client, _index_name
        es = _get_client()
        if es:
            resp = es.search(
                index=_index_name(tenant),
                body={
                    "suggest": {
                        "text": query,
                        "simple_phrase": {
                            "phrase": {
                                "field":          "name",
                                "size":           1,
                                "gram_size":      3,
                                "direct_generator":[{"field":"name","suggest_mode":"missing"}],
                            }
                        }
                    },
                    "size": 0,
                }
            )
            suggestions = resp.get("suggest",{}).get("simple_phrase",[])
            if suggestions and suggestions[0].get("options"):
                corrected = suggestions[0]["options"][0]["text"]
                if corrected != query:
                    logger.debug("[Spell] '%s' → '%s'", query, corrected)
                    return corrected
    except Exception:
        pass

    return query


def did_you_mean(query: str, tenant) -> dict:
    corrected = correct_query(query, tenant)
    return {
        "original": query,
        "corrected": corrected,
        "has_correction": corrected != query,
    }
