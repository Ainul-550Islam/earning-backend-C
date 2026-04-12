"""MARKETPLACE_SAFETY/content_moderation.py — Text content moderation"""
PROHIBITED_WORDS = [
    "fake", "counterfeit", "replica", "pirated",
    "illegal", "banned", "stolen",
]


def moderate_text(text: str) -> dict:
    """Returns {"clean": bool, "flagged_words": list}"""
    text_lower = text.lower()
    flagged = [w for w in PROHIBITED_WORDS if w in text_lower]
    return {"clean": len(flagged) == 0, "flagged_words": flagged}


def moderate_product(product) -> dict:
    name_result = moderate_text(product.name)
    desc_result = moderate_text(product.description)
    return {
        "product_id": product.id,
        "name_clean": name_result["clean"],
        "description_clean": desc_result["clean"],
        "flagged": name_result["flagged_words"] + desc_result["flagged_words"],
    }
