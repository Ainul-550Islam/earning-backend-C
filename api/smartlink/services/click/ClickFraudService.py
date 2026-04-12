import logging
from django.core.cache import cache
from ...constants import (
    FRAUD_SCORE_FLAG_THRESHOLD, FRAUD_SCORE_BLOCK_THRESHOLD,
    MAX_CLICKS_PER_IP_PER_HOUR, MAX_CLICKS_PER_IP_PER_DAY,
)
from ...enums import FraudSignalType, FraudAction
from .BotDetectionService import BotDetectionService

logger = logging.getLogger('smartlink.fraud')


class ClickFraudService:
    """
    Multi-signal fraud scoring for clicks.
    Returns fraud score (0-100) and list of detected signals.
    Score >= 85 → block. Score >= 60 → flag for review.
    """

    def __init__(self):
        self.bot_service = BotDetectionService()

    def score(self, ip: str, user_agent: str, context: dict) -> tuple:
        """
        Score a click for fraud signals.

        Returns:
            (fraud_score: int, signals: list[FraudSignalType])
        """
        signals = []
        score = 0

        # Signal 1: IP velocity (too many clicks from same IP)
        ip_velocity_score = self._check_ip_velocity(ip)
        if ip_velocity_score > 0:
            score += ip_velocity_score
            signals.append(FraudSignalType.HIGH_VELOCITY)

        # Signal 2: Known bad IP / blocklist
        if self._is_known_bad_ip(ip):
            score += 40
            signals.append(FraudSignalType.KNOWN_BAD_IP)

        # Signal 3: Datacenter / hosting IP
        if self._is_datacenter_ip(ip, context):
            score += 25
            signals.append(FraudSignalType.DATACENTER_IP)

        # Signal 4: Bot User-Agent
        is_bot, _ = self.bot_service.detect(ip, user_agent)
        if is_bot:
            score += 50
            signals.append(FraudSignalType.BOT_UA)

        # Signal 5: Invalid / empty User-Agent
        if not user_agent or len(user_agent) < 10:
            score += 20
            signals.append(FraudSignalType.INVALID_UA)

        # Signal 6: Headless browser
        if self._is_headless(user_agent):
            score += 45
            signals.append(FraudSignalType.HEADLESS_BROWSER)

        # Signal 7: Proxy/VPN detection (ASN-based)
        if self._is_proxy_or_vpn(context):
            score += 15
            signals.append(FraudSignalType.PROXY_VPN)

        # Cap at 100
        score = min(score, 100)

        if score >= FRAUD_SCORE_BLOCK_THRESHOLD:
            action = FraudAction.BLOCK
            self._flag_ip(ip)
        elif score >= FRAUD_SCORE_FLAG_THRESHOLD:
            action = FraudAction.FLAG
        else:
            action = FraudAction.ALLOW

        if signals:
            logger.debug(
                f"Fraud score={score} action={action} ip={ip} signals={signals}"
            )

        return score, signals

    def create_fraud_flag(self, click, score: int, signals: list, action: str):
        """Persist a ClickFraudFlag record for a flagged/blocked click."""
        from ...models import ClickFraudFlag
        try:
            ClickFraudFlag.objects.create(
                click=click,
                score=score,
                signals=[s.value if hasattr(s, 'value') else s for s in signals],
                action_taken=action,
            )
        except Exception as e:
            logger.warning(f"Failed to create fraud flag: {e}")

    # ── Private fraud signal detectors ────────────────────────────────

    def _check_ip_velocity(self, ip: str) -> int:
        """Check clicks-per-hour and clicks-per-day for this IP."""
        hour_key = f"fraud:velocity:hour:{ip}"
        day_key = f"fraud:velocity:day:{ip}"

        hour_count = cache.get(hour_key, 0)
        day_count = cache.get(day_key, 0)

        # Increment counters
        try:
            cache.incr(hour_key)
        except ValueError:
            cache.set(hour_key, 1, 3600)
        try:
            cache.incr(day_key)
        except ValueError:
            cache.set(day_key, 1, 86400)

        if hour_count >= MAX_CLICKS_PER_IP_PER_HOUR:
            return 35
        if day_count >= MAX_CLICKS_PER_IP_PER_DAY:
            return 25
        return 0

    def _is_known_bad_ip(self, ip: str) -> bool:
        """Check if IP is in the bad IP blocklist (Redis set)."""
        return bool(cache.get(f"fraud:blocked:{ip}"))

    def _is_datacenter_ip(self, ip: str, context: dict) -> bool:
        """
        Heuristic: ASN belongs to well-known datacenter providers.
        """
        datacenter_asns = {
            'AS14618', 'AS16509',  # Amazon AWS
            'AS15169', 'AS396982',  # Google Cloud
            'AS8075',               # Microsoft Azure
            'AS13335',              # Cloudflare
            'AS20473',              # Vultr
            'AS14061',              # DigitalOcean
            'AS63949',              # Linode
        }
        asn = context.get('asn', '')
        return asn in datacenter_asns

    def _is_headless(self, user_agent: str) -> bool:
        """Detect headless browsers used by bots."""
        headless_indicators = [
            'headlesschrome', 'phantomjs', 'selenium',
            'webdriver', 'puppeteer', 'playwright',
        ]
        ua_lower = user_agent.lower()
        return any(h in ua_lower for h in headless_indicators)

    def _is_proxy_or_vpn(self, context: dict) -> bool:
        """
        Basic proxy/VPN detection via ASN.
        More sophisticated check would use an IP intelligence API.
        """
        vpn_asns = {
            'AS9009',  # M247 (common VPN provider)
            'AS60068',  # CDN77
        }
        return context.get('asn', '') in vpn_asns

    def _flag_ip(self, ip: str, ttl: int = 3600):
        """Add IP to fraud blocklist in Redis."""
        cache.set(f"fraud:blocked:{ip}", '1', ttl)
        logger.info(f"IP flagged as fraud: {ip}")
