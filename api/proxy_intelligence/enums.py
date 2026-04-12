from django.db import models


class ProxyType(models.TextChoices):
    RESIDENTIAL = 'residential', 'Residential Proxy'
    DATACENTER = 'datacenter', 'Datacenter Proxy'
    MOBILE = 'mobile', 'Mobile Proxy'
    SOCKS4 = 'socks4', 'SOCKS4'
    SOCKS5 = 'socks5', 'SOCKS5'
    HTTP = 'http', 'HTTP Proxy'
    HTTPS = 'https', 'HTTPS Proxy'
    TOR = 'tor', 'Tor Exit Node'
    UNKNOWN = 'unknown', 'Unknown'


class RiskLevel(models.TextChoices):
    VERY_LOW = 'very_low', 'Very Low (0-20)'
    LOW = 'low', 'Low (21-40)'
    MEDIUM = 'medium', 'Medium (41-60)'
    HIGH = 'high', 'High (61-80)'
    CRITICAL = 'critical', 'Critical (81-100)'


class DetectionStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    DETECTED = 'detected', 'Detected'
    CLEAN = 'clean', 'Clean'
    WHITELISTED = 'whitelisted', 'Whitelisted'
    BLACKLISTED = 'blacklisted', 'Blacklisted'


class ThreatType(models.TextChoices):
    MALWARE = 'malware', 'Malware'
    BOTNET = 'botnet', 'Botnet'
    SPAM = 'spam', 'Spam'
    PHISHING = 'phishing', 'Phishing'
    SCANNER = 'scanner', 'Scanner'
    BRUTE_FORCE = 'brute_force', 'Brute Force'
    DDoS = 'ddos', 'DDoS'
    TOR = 'tor', 'Tor'
    VPN = 'vpn', 'VPN'
    PROXY = 'proxy', 'Proxy'


class IPVersion(models.TextChoices):
    IPv4 = 'ipv4', 'IPv4'
    IPv6 = 'ipv6', 'IPv6'


class BlacklistReason(models.TextChoices):
    FRAUD = 'fraud', 'Fraud Detected'
    ABUSE = 'abuse', 'Abuse Reported'
    SPAM = 'spam', 'Spam Activity'
    BOT = 'bot', 'Bot Activity'
    SCRAPING = 'scraping', 'Scraping'
    MANUAL = 'manual', 'Manual Block'
    THREAT_FEED = 'threat_feed', 'Threat Feed'
    RATE_LIMIT = 'rate_limit', 'Rate Limit Exceeded'
