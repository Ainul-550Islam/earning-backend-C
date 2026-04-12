"""
MARKETPLACE_SAFETY/restricted_items.py — Restricted Item Policy
"""
RESTRICTED_KEYWORDS = {
    "weapons":    ["gun","pistol","rifle","ammunition","grenade","explosive","bomb","weapon"],
    "drugs":      ["marijuana","cannabis","cocaine","heroin","meth","narcotic","opium"],
    "counterfeit":["fake","replica","copy","counterfeit","pirated","forged"],
    "hacking":    ["malware","exploit","hack","cracking","ddos","keylogger"],
    "gambling":   ["casino","betting","lottery","gambling","poker chip"],
    "human":      ["organ","blood","human part","specimen"],
}

RESTRICTED_BY_CATEGORY = {
    "firearms_accessories": {"requires_license": True, "license_type": "firearms_dealer"},
    "medical_devices":      {"requires_license": True, "license_type": "medical_device_seller"},
    "food_supplements":     {"requires_certification": True, "cert_type": "BSTI"},
    "electronics":          {"requires_warranty_docs": True},
}


def check_restricted_content(product) -> dict:
    text = f"{product.name} {product.description}".lower()
    violations = []

    for category, keywords in RESTRICTED_KEYWORDS.items():
        found = [kw for kw in keywords if kw in text]
        if found:
            violations.append({
                "category": category,
                "keywords": found,
                "action":   "block" if category in ("weapons","drugs","human") else "review",
            })

    blocked    = any(v["action"] == "block" for v in violations)
    needs_review = not blocked and bool(violations)

    return {
        "product_id":   product.pk,
        "blocked":      blocked,
        "needs_review": needs_review,
        "violations":   violations,
    }


def get_required_documents(category_slug: str) -> list:
    requirements = RESTRICTED_BY_CATEGORY.get(category_slug, {})
    docs = []
    if requirements.get("requires_license"):
        docs.append(f"License: {requirements['license_type']}")
    if requirements.get("requires_certification"):
        docs.append(f"Certification: {requirements['cert_type']}")
    if requirements.get("requires_warranty_docs"):
        docs.append("Warranty documentation required")
    return docs
