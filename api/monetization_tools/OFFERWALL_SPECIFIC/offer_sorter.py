"""OFFERWALL_SPECIFIC/offer_sorter.py — Offer sorting strategies."""


class OfferSorter:
    STRATEGIES = ["point_value", "payout", "newest", "featured", "popularity"]

    @classmethod
    def sort(cls, offers: list, strategy: str = "point_value",
              featured_first: bool = True) -> list:
        if featured_first:
            featured = [o for o in offers if getattr(o, "is_featured", False)]
            rest     = [o for o in offers if not getattr(o, "is_featured", False)]
        else:
            featured, rest = [], list(offers)

        key_map = {
            "point_value": lambda o: getattr(o, "point_value", 0),
            "payout":      lambda o: getattr(o, "payout_amount", 0),
            "newest":      lambda o: getattr(o, "created_at", 0),
            "popularity":  lambda o: getattr(o, "total_completions", 0),
        }
        key = key_map.get(strategy, key_map["point_value"])
        rest.sort(key=key, reverse=True)
        return featured + rest

    @classmethod
    def paginate(cls, offers: list, page: int = 1, per_page: int = 10) -> dict:
        start  = (page - 1) * per_page
        end    = start + per_page
        total  = len(offers)
        return {
            "results":    offers[start:end],
            "page":       page, "per_page": per_page,
            "total":      total, "pages": (total + per_page - 1) // per_page,
        }
