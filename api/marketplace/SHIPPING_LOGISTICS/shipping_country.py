"""
SHIPPING_LOGISTICS/shipping_country.py — Country Shipping Configuration
"""
SUPPORTED_COUNTRIES = {
    "BD": {"name": "Bangladesh", "currency": "BDT", "vat_rate": 0.15, "cod_supported": True},
    "IN": {"name": "India",      "currency": "INR", "vat_rate": 0.18, "cod_supported": True},
    "PK": {"name": "Pakistan",   "currency": "PKR", "vat_rate": 0.17, "cod_supported": True},
    "LK": {"name": "Sri Lanka",  "currency": "LKR", "vat_rate": 0.08, "cod_supported": False},
    "NP": {"name": "Nepal",      "currency": "NPR", "vat_rate": 0.13, "cod_supported": False},
    "GB": {"name": "UK",         "currency": "GBP", "vat_rate": 0.20, "cod_supported": False},
    "US": {"name": "USA",        "currency": "USD", "vat_rate": 0.10, "cod_supported": False},
}

INTERNATIONAL_SHIPPING_RATES = {
    "south_asia": {"rate_per_kg": 1200, "min_rate": 1500, "days": "7-14"},
    "rest_of_world": {"rate_per_kg": 2500, "min_rate": 3000, "days": "14-21"},
}

def get_country_config(country_code: str) -> dict:
    return SUPPORTED_COUNTRIES.get(country_code.upper(), {})

def calculate_international_rate(country_code: str, weight_kg: float) -> dict:
    south_asia = {"IN","PK","LK","NP","BT","MV","AF"}
    region = "south_asia" if country_code in south_asia else "rest_of_world"
    cfg = INTERNATIONAL_SHIPPING_RATES[region]
    rate = max(cfg["min_rate"], cfg["rate_per_kg"] * weight_kg)
    return {"region": region, "rate": rate, "currency": "BDT", "est_days": cfg["days"]}

def is_cod_available(country_code: str) -> bool:
    return SUPPORTED_COUNTRIES.get(country_code, {}).get("cod_supported", False)
