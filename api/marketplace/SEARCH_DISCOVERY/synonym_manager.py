"""
SEARCH_DISCOVERY/synonym_manager.py — Search Synonym Management
"""
from django.db import models


class SearchSynonym(models.Model):
    tenant     = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True,
                                    related_name="search_synonyms_tenant")
    term       = models.CharField(max_length=100)
    synonyms   = models.TextField(help_text="Comma-separated synonyms")
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "marketplace"
        db_table  = "marketplace_search_synonym"
        unique_together = [("tenant","term")]

    def get_synonyms(self) -> list:
        return [s.strip() for s in self.synonyms.split(",") if s.strip()]


BD_DEFAULT_SYNONYMS = {
    "phone": ["mobile","smartphone","handset","মোবাইল"],
    "shirt": ["t-shirt","polo","top","tops"],
    "pants": ["trouser","jeans","legging","bottom"],
    "shoes": ["footwear","sneakers","sandals","boots"],
    "laptop": ["notebook","computer","pc"],
    "tv":    ["television","monitor","display","screen"],
}


def seed_synonyms(tenant):
    for term, syns in BD_DEFAULT_SYNONYMS.items():
        SearchSynonym.objects.get_or_create(
            tenant=tenant, term=term,
            defaults={"synonyms": ", ".join(syns)}
        )


def expand_query(query: str, tenant) -> list:
    """Expand query with known synonyms."""
    terms = [query]
    try:
        for syn in SearchSynonym.objects.filter(tenant=tenant, is_active=True):
            if syn.term.lower() in query.lower():
                terms.extend(syn.get_synonyms())
            elif any(s.lower() in query.lower() for s in syn.get_synonyms()):
                terms.append(syn.term)
    except Exception:
        pass
    return list(set(terms))


def get_synonym_list(tenant) -> list:
    return list(SearchSynonym.objects.filter(tenant=tenant, is_active=True).values("term","synonyms"))
