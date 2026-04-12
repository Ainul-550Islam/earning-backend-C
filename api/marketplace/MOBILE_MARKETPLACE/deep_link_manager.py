"""
MOBILE_MARKETPLACE/deep_link_manager.py — Deep Link Generation & Routing
"""
from urllib.parse import urlencode

BASE_SCHEME = "marketplace"   # marketplace://

ROUTES = {
    "product":    "{scheme}://product/{id}",
    "category":   "{scheme}://category/{slug}",
    "order":      "{scheme}://order/{order_number}",
    "seller":     "{scheme}://seller/{store_slug}",
    "cart":       "{scheme}://cart",
    "profile":    "{scheme}://profile",
    "promotion":  "{scheme}://promotion/{slug}",
    "dispute":    "{scheme}://dispute/{id}",
    "search":     "{scheme}://search?q={query}",
    "referral":   "{scheme}://referral/{code}",
}

def product_link(product_id: int) -> str:
    return ROUTES["product"].format(scheme=BASE_SCHEME, id=product_id)

def category_link(slug: str) -> str:
    return ROUTES["category"].format(scheme=BASE_SCHEME, slug=slug)

def order_link(order_number: str) -> str:
    return ROUTES["order"].format(scheme=BASE_SCHEME, order_number=order_number)

def seller_link(store_slug: str) -> str:
    return ROUTES["seller"].format(scheme=BASE_SCHEME, store_slug=store_slug)

def search_link(query: str) -> str:
    return ROUTES["search"].format(scheme=BASE_SCHEME, query=query)

def referral_link(code: str) -> str:
    return ROUTES["referral"].format(scheme=BASE_SCHEME, code=code)

def promotion_link(slug: str) -> str:
    return ROUTES["promotion"].format(scheme=BASE_SCHEME, slug=slug)

def generate_share_url(product, base_web_url: str = "") -> dict:
    """Generate both deep link and web URL for sharing."""
    deep = product_link(product.pk)
    web  = f"{base_web_url}/products/{product.slug}/" if base_web_url else ""
    return {
        "deep_link": deep,
        "web_url":   web,
        "share_text": f"Check out {product.name} — {web or deep}",
    }

def resolve_link(deep_link: str) -> dict:
    """Parse incoming deep link → return route info."""
    import re
    link = deep_link.replace(f"{BASE_SCHEME}://", "")
    patterns = [
        (r"^product/(\d+)$",          "product",   {"id": r"\1"}),
        (r"^category/([\w-]+)$",      "category",  {"slug": r"\1"}),
        (r"^order/([\w\d]+)$",        "order",     {"order_number": r"\1"}),
        (r"^seller/([\w-]+)$",        "seller",    {"store_slug": r"\1"}),
        (r"^promotion/([\w-]+)$",     "promotion", {"slug": r"\1"}),
        (r"^referral/([\w\d]+)$",     "referral",  {"code": r"\1"}),
        (r"^search\?q=(.+)$",         "search",    {"query": r"\1"}),
    ]
    for pattern, route, param_template in patterns:
        m = re.match(pattern, link)
        if m:
            params = {k: re.sub(pattern, v, link) for k, v in param_template.items()}
            return {"route": route, "params": params}
    return {"route": "home", "params": {}}
