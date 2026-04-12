"""
SEARCH_DISCOVERY/sort_manager.py — Product Sort Options
"""

SORT_OPTIONS = [
    {"key": "relevance",  "label": "Most Relevant",   "orm": "-total_sales"},
    {"key": "price_asc",  "label": "Price: Low to High","orm": "base_price"},
    {"key": "price_desc", "label": "Price: High to Low","orm": "-base_price"},
    {"key": "rating",     "label": "Top Rated",        "orm": "-average_rating"},
    {"key": "newest",     "label": "Newest First",     "orm": "-created_at"},
    {"key": "sales",      "label": "Best Selling",     "orm": "-total_sales"},
    {"key": "discount",   "label": "Biggest Discount",  "orm": "sale_price"},
]

ORM_SORT_MAP = {opt["key"]: opt["orm"] for opt in SORT_OPTIONS}


def get_sort_options() -> list:
    return SORT_OPTIONS


def apply_sort(qs, sort_key: str = "relevance"):
    orm_field = ORM_SORT_MAP.get(sort_key, "-total_sales")
    return qs.order_by(orm_field)


def get_es_sort(sort_key: str) -> list:
    es_sorts = {
        "relevance":  ["_score", {"total_sales": "desc"}],
        "price_asc":  [{"effective_price": "asc"}],
        "price_desc": [{"effective_price": "desc"}],
        "rating":     [{"average_rating": "desc"}],
        "newest":     [{"created_at": "desc"}],
        "sales":      [{"total_sales": "desc"}],
    }
    return es_sorts.get(sort_key, es_sorts["relevance"])
