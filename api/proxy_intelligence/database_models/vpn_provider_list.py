"""VPN Provider List — manages the known VPN provider database."""
from django.core.cache import cache

VPN_PROVIDERS = {
    "NordVPN":        {"asns": ["AS44814", "AS212238"], "risk": "high"},
    "ExpressVPN":     {"asns": ["AS9009", "AS212238"],  "risk": "high"},
    "Mullvad":        {"asns": ["AS39351", "AS209103"], "risk": "high"},
    "ProtonVPN":      {"asns": ["AS207990", "AS62240"], "risk": "high"},
    "PIA":            {"asns": ["AS46484"],             "risk": "high"},
    "Surfshark":      {"asns": ["AS16247"],             "risk": "high"},
    "CyberGhost":     {"asns": ["AS31898"],             "risk": "high"},
    "IPVanish":       {"asns": ["AS36236"],             "risk": "high"},
    "HideMyAss":      {"asns": ["AS16276"],             "risk": "high"},
    "TunnelBear":     {"asns": ["AS46652"],             "risk": "high"},
    "Windscribe":     {"asns": ["AS55286"],             "risk": "high"},
    "HotspotShield":  {"asns": ["AS394089"],            "risk": "high"},
    "M247":           {"asns": ["AS9009"],              "risk": "high"},
    "Clouvider":      {"asns": ["AS62240"],             "risk": "high"},
    "G-CoreLabs":     {"asns": ["AS202422"],            "risk": "medium"},
}

# Build reverse map: ASN → provider name
ASN_TO_PROVIDER = {
    asn: name
    for name, info in VPN_PROVIDERS.items()
    for asn in info["asns"]
}


class VPNProviderList:
    @staticmethod
    def identify_by_asn(asn: str) -> str:
        return ASN_TO_PROVIDER.get(asn.upper().strip(), "")

    @staticmethod
    def is_known_vpn_asn(asn: str) -> bool:
        return asn.upper().strip() in ASN_TO_PROVIDER

    @staticmethod
    def get_all_providers() -> dict:
        return VPN_PROVIDERS

    @staticmethod
    def get_all_asns() -> list:
        return list(ASN_TO_PROVIDER.keys())

    @staticmethod
    def get_high_risk_providers() -> list:
        return [n for n, info in VPN_PROVIDERS.items() if info.get("risk") == "high"]

    @staticmethod
    def provider_count() -> int:
        return len(VPN_PROVIDERS)

    @staticmethod
    def add_provider(name: str, asns: list, risk: str = "high"):
        """Register a new VPN provider."""
        VPN_PROVIDERS[name] = {"asns": asns, "risk": risk}
        for asn in asns:
            ASN_TO_PROVIDER[asn.upper()] = name
