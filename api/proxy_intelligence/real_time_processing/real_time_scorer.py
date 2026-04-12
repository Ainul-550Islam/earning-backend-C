"""
Real-Time Scorer
=================
Performs sub-100ms risk scoring for live API requests.
Uses cached data and lightweight checks only.
"""
import logging
from django.core.cache import cache
from ..cache import PICache
from ..enums import RiskLevel

logger = logging.getLogger(__name__)


class RealTimeScorer:
    """
    Fast risk scoring designed for use in middleware or request handlers.
    Relies entirely on cached data — never makes external API calls.
    Falls back gracefully if cache is cold.
    """

    def __init__(self, ip_address: str, user=None, tenant=None):
        self.ip_address = ip_address
        self.user = user
        self.tenant = tenant
        self.score = 0
        self.flags = []

    def score_request(self) -> dict:
        """Score the current request in real-time using only cached data."""
        self._check_blacklist()
        if self.score >= 100:
            return self._result('block')

        self._check_whitelist()
        if self.score < 0:
            return self._result('allow')

        self._check_cached_intelligence()
        self._check_user_risk()

        action = self._determine_action()
        return self._result(action)

    def _check_blacklist(self):
        is_bl = PICache.is_blacklisted(self.ip_address)
        if is_bl:
            self.score = 100
            self.flags.append('blacklisted')

    def _check_whitelist(self):
        is_wl = PICache.is_whitelisted(self.ip_address)
        if is_wl:
            self.score = -1  # Signal: skip all other checks
            self.flags.append('whitelisted')

    def _check_cached_intelligence(self):
        intel = PICache.get_intelligence(self.ip_address)
        if intel:
            self.score = intel.get('risk_score', 0)
            if intel.get('is_tor'):
                self.flags.append('tor')
            if intel.get('is_vpn'):
                self.flags.append('vpn')
            if intel.get('is_proxy'):
                self.flags.append('proxy')
            if intel.get('is_datacenter'):
                self.flags.append('datacenter')
        else:
            # Cache cold — check DB
            try:
                from ..models import IPIntelligence
                obj = IPIntelligence.objects.filter(
                    ip_address=self.ip_address
                ).values('risk_score', 'is_tor', 'is_vpn', 'is_proxy').first()
                if obj:
                    self.score = obj['risk_score']
                    PICache.set_intelligence(self.ip_address, obj)
            except Exception:
                pass

    def _check_user_risk(self):
        if not self.user or not self.user.is_authenticated:
            return
        try:
            from ..models import UserRiskProfile
            profile = UserRiskProfile.objects.filter(user=self.user).values(
                'overall_risk_score', 'is_high_risk'
            ).first()
            if profile and profile['is_high_risk']:
                self.score = min(self.score + 20, 100)
                self.flags.append('high_risk_user')
        except Exception:
            pass

    def _determine_action(self) -> str:
        if self.score >= 81:
            return 'block'
        elif self.score >= 61:
            return 'challenge'
        elif self.score >= 41:
            return 'flag'
        return 'allow'

    def _result(self, action: str) -> dict:
        return {
            'ip_address': self.ip_address,
            'risk_score': max(self.score, 0),
            'risk_level': self._level(),
            'action': action,
            'flags': self.flags,
            'is_blocked': action == 'block',
        }

    def _level(self) -> str:
        s = self.score
        if s <= 0:
            return RiskLevel.VERY_LOW
        elif s <= 20:
            return RiskLevel.VERY_LOW
        elif s <= 40:
            return RiskLevel.LOW
        elif s <= 60:
            return RiskLevel.MEDIUM
        elif s <= 80:
            return RiskLevel.HIGH
        return RiskLevel.CRITICAL
