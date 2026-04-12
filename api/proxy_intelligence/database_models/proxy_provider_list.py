"""Proxy Provider List — known residential/datacenter proxy providers."""

PROXY_PROVIDERS = {
    "BrightData": {
        "keywords": ["brightdata", "luminati"],
        "type": "residential",
        "risk": "high",
    },
    "Oxylabs": {
        "keywords": ["oxylabs"],
        "type": "residential",
        "risk": "high",
    },
    "SmartProxy": {
        "keywords": ["smartproxy"],
        "type": "residential",
        "risk": "high",
    },
    "NetNut": {
        "keywords": ["netnut"],
        "type": "residential",
        "risk": "high",
    },
    "IPRoyal": {
        "keywords": ["iproyal"],
        "type": "residential",
        "risk": "high",
    },
    "Squid": {
        "keywords": ["squid"],
        "type": "http",
        "risk": "medium",
    },
    "Privoxy": {
        "keywords": ["privoxy"],
        "type": "http",
        "risk": "medium",
    },
}


class ProxyProviderList:
    @staticmethod
    def identify(isp: str) -> dict:
        isp_lower = isp.lower()
        for name, info in PROXY_PROVIDERS.items():
            if any(kw in isp_lower for kw in info["keywords"]):
                return {"provider": name, "type": info["type"], "risk": info["risk"]}
        return {}

    @staticmethod
    def get_all() -> dict:
        return PROXY_PROVIDERS

    @staticmethod
    def get_high_risk_providers() -> list:
        return [name for name, info in PROXY_PROVIDERS.items() if info["risk"] == "high"]
