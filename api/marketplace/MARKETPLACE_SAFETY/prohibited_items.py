"""
MARKETPLACE_SAFETY/prohibited_items.py — Prohibited Items Policy
"""
from django.db import models


PROHIBITED_CATEGORIES = [
    "weapons","firearms","ammunition","explosives",
    "illegal_drugs","narcotics","controlled_substances",
    "human_organs","blood_products",
    "adult_content","obscene_material",
    "gambling_equipment","lottery_tickets",
    "counterfeit_currency","forged_documents",
    "stolen_goods","illegal_services",
]

PROHIBITED_KEYWORDS = [
    "gun","pistol","rifle","revolver","shotgun","ammo","ammunition",
    "grenade","bomb","explosive","dynamite","tnt",
    "heroin","cocaine","meth","marijuana","weed","ganja","crack","opium",
    "human organ","kidney for sale","blood for sale",
    "stolen","fake passport","counterfeit","forged",
    "child","minor","underage","nude",
    "hack","ddos","malware","ransomware","exploit",
]

RESTRICTED_KEYWORDS = [
    "prescription","controlled substance","age restricted","18+",
    "alcohol","tobacco","cigarette","vape","e-cigarette",
    "firework","pyrotechnic","replica","airsoft",
]

CATEGORY_RESTRICTIONS = {
    "medicine":         {"requires_prescription": True, "license_required": "pharmacy"},
    "medical_devices":  {"requires_certification": True, "cert_type": "BSTI_medical"},
    "food_supplements": {"requires_certification": True, "cert_type": "BSTI"},
    "electronics":      {"requires_warranty": True},
    "food_beverage":    {"requires_bsti": True},
    "cosmetics":        {"requires_bsti": True},
}


def is_prohibited(product_name: str, description: str = "", category_slug: str = "") -> dict:
    """
    Check if a product is prohibited.
    Returns {"prohibited": bool, "reason": str, "keywords": list}
    """
    text  = f"{product_name} {description}".lower()
    flags = []

    if category_slug in PROHIBITED_CATEGORIES:
        flags.append(f"Category '{category_slug}' is prohibited")

    found_keywords = [kw for kw in PROHIBITED_KEYWORDS if kw in text]
    if found_keywords:
        flags.append(f"Contains prohibited keywords: {', '.join(found_keywords)}")

    return {
        "prohibited": len(flags) > 0,
        "reason":     "; ".join(flags),
        "keywords":   found_keywords,
    }


def is_restricted(product_name: str, description: str = "", category_slug: str = "") -> dict:
    """
    Check if a product is restricted (allowed but requires documentation).
    """
    text     = f"{product_name} {description}".lower()
    flags    = [kw for kw in RESTRICTED_KEYWORDS if kw in text]
    reqs     = CATEGORY_RESTRICTIONS.get(category_slug, {})
    return {
        "restricted":    len(flags) > 0 or bool(reqs),
        "keywords":      flags,
        "requirements":  reqs,
    }


def scan_listing(product) -> dict:
    """Full policy scan for a product listing."""
    prohibited = is_prohibited(product.name, product.description,
                                product.category.slug if product.category else "")
    restricted = is_restricted(product.name, product.description,
                                product.category.slug if product.category else "")
    return {
        "product_id":  product.pk,
        "prohibited":  prohibited["prohibited"],
        "restricted":  restricted["restricted"],
        "can_list":    not prohibited["prohibited"],
        "flags":       prohibited["keywords"] + restricted["keywords"],
        "requirements":restricted["requirements"],
        "reason":      prohibited["reason"],
    }


def get_allowed_categories() -> list:
    return [
        "electronics","fashion","home_living","sports","books","food","toys",
        "beauty","health","baby","automotive","garden","pets","office",
        "travel","music","art","photography","software","courses",
    ]
