"""
SHIPPING_LOGISTICS/shipping_city.py — Bangladesh City / Area Database
"""
BD_CITIES = {
    "Dhaka":      {"district": "Dhaka",      "division": "Dhaka",     "postcode": "1000"},
    "Chittagong": {"district": "Chittagong", "division": "Chittagong","postcode": "4000"},
    "Rajshahi":   {"district": "Rajshahi",   "division": "Rajshahi",  "postcode": "6000"},
    "Khulna":     {"district": "Khulna",     "division": "Khulna",    "postcode": "9000"},
    "Sylhet":     {"district": "Sylhet",     "division": "Sylhet",    "postcode": "3100"},
    "Barisal":    {"district": "Barisal",    "division": "Barisal",   "postcode": "8200"},
    "Rangpur":    {"district": "Rangpur",    "division": "Rangpur",   "postcode": "5400"},
    "Mymensingh": {"district": "Mymensingh", "division": "Mymensingh","postcode": "2200"},
    "Comilla":    {"district": "Comilla",    "division": "Chittagong","postcode": "3500"},
    "Narayanganj":{"district": "Narayanganj","division": "Dhaka",     "postcode": "1400"},
    "Gazipur":    {"district": "Gazipur",    "division": "Dhaka",     "postcode": "1700"},
}

def get_city_info(city_name: str) -> dict:
    return BD_CITIES.get(city_name, {})

def search_cities(query: str) -> list:
    q = query.lower()
    return [{"city": k, **v} for k, v in BD_CITIES.items() if q in k.lower()]

def get_postcode(city: str) -> str:
    return BD_CITIES.get(city, {}).get("postcode", "")
