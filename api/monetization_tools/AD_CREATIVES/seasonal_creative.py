"""AD_CREATIVES/seasonal_creative.py — Seasonal campaign creative switcher."""
from datetime import date


SEASONAL_THEMES = {
    "eid_ul_fitr":   {"months": [3, 4],    "keywords": ["eid", "celebration"]},
    "eid_ul_adha":   {"months": [6, 7],    "keywords": ["eid", "qurbani"]},
    "ramadan":       {"months": [3, 4],    "keywords": ["ramadan", "iftar"]},
    "new_year":      {"months": [1],       "keywords": ["new year", "celebrate"]},
    "independence":  {"months": [3, 8, 12],"keywords": ["national day"]},
    "valentines":    {"months": [2],       "keywords": ["love", "gift"]},
    "christmas":     {"months": [12],      "keywords": ["christmas", "holiday"]},
    "black_friday":  {"months": [11],      "keywords": ["discount", "sale"]},
}

SEASONAL_MULTIPLIERS = {
    "eid_ul_fitr":  1.8,
    "ramadan":      1.5,
    "black_friday": 2.0,
    "christmas":    1.7,
    "new_year":     1.4,
}


class SeasonalCreativeManager:
    """Activates seasonal creative themes based on current date."""

    @classmethod
    def active_season(cls, d: date = None) -> str:
        d = d or date.today()
        for season, info in SEASONAL_THEMES.items():
            if d.month in info["months"]:
                return season
        return "default"

    @classmethod
    def get_multiplier(cls, d: date = None) -> float:
        return SEASONAL_MULTIPLIERS.get(cls.active_season(d), 1.0)

    @classmethod
    def get_theme_keywords(cls, d: date = None) -> list:
        season = cls.active_season(d)
        return SEASONAL_THEMES.get(season, {}).get("keywords", [])

    @classmethod
    def apply_seasonal_theme(cls, creative_config: dict, d: date = None) -> dict:
        season   = cls.active_season(d)
        result   = dict(creative_config)
        result["season"]            = season
        result["revenue_multiplier"] = cls.get_multiplier(d)
        result["theme_keywords"]    = cls.get_theme_keywords(d)
        return result
