# api/cms/adapters/fraud_security.py
"""
Adapters for api.fraud_detection, api.security, api.kyc, api.proxy_intelligence

  FraudAdapter   — fraud scoring, sanctions, block checks
  SecurityAdapter— 2FA, session security
  KYCAdapter     — KYC status checks
  ProxyAdapter   — IP/proxy intelligence
"""
import logging
from typing import Optional, Dict, Any

from .base import BaseAdapter

logger = logging.getLogger('api.cms.adapters')


class FraudAdapter(BaseAdapter):
    """CMS → api.fraud_detection interface."""

    _system_name = 'api.fraud_detection'

    @classmethod
    def _check_available(cls):
        import api.fraud_detection  # noqa

    @classmethod
    def check_user(cls, user, action: str = 'cms_action') -> Dict:
        """
        Get a fraud risk assessment for a user action.
        Returns {'allowed': bool, 'score': float, 'reason': str}
        """
        try:
            from api.fraud_detection.services import FraudService
            result = FraudService.assess(user=user, action=action)
            return result or {'allowed': True, 'score': 0.0, 'reason': ''}
        except ImportError:
            return {'allowed': True, 'score': 0.0, 'reason': 'fraud_detection_unavailable'}
        except Exception as e:
            logger.warning("[CMS→Fraud] check_user failed: %s", e)
            return {'allowed': True, 'score': 0.0, 'reason': 'error'}

    @classmethod
    def is_sanctioned(cls, user) -> bool:
        """Check if user appears on a sanctions list."""
        try:
            from api.fraud_detection.models import SanctionList
            return SanctionList.objects.filter(user=user, is_active=True).exists()
        except ImportError:
            return False
        except Exception:
            return False

    @classmethod
    def check_ip(cls, ip_address: str) -> Dict:
        """
        Check an IP address for fraud signals.
        Returns {'blocked': bool, 'proxy': bool, 'vpn': bool, 'country': str}
        """
        try:
            from api.fraud_detection.services import FraudService
            return FraudService.check_ip(ip=ip_address) or {'blocked': False}
        except ImportError:
            return {'blocked': False}
        except Exception:
            return {'blocked': False}

    @classmethod
    def report_suspicious(cls, user, reason: str, data: Optional[Dict] = None) -> bool:
        """Flag a user action as suspicious for review."""
        try:
            from api.fraud_detection.services import FraudService
            FraudService.flag(user=user, reason=reason, data=data or {})
            return True
        except (ImportError, Exception):
            return False


class SecurityAdapter(BaseAdapter):
    """CMS → api.security interface."""

    _system_name = 'api.security'

    @classmethod
    def _check_available(cls):
        import api.security  # noqa

    @classmethod
    def requires_2fa(cls, user) -> bool:
        """Check if this user requires 2FA for sensitive CMS actions."""
        try:
            from api.security.models import UserSecurity
            sec = UserSecurity.objects.filter(user=user).first()
            return getattr(sec, 'two_factor_enabled', False) if sec else False
        except ImportError:
            return False
        except Exception:
            return False

    @classmethod
    def verify_2fa_token(cls, user, token: str) -> bool:
        """Verify a TOTP/2FA token for a user."""
        try:
            from api.security.services import TwoFactorService
            return TwoFactorService.verify(user=user, token=token)
        except ImportError:
            return True  # open if 2FA system not available
        except Exception:
            return False

    @classmethod
    def log_security_event(cls, user, event_type: str, ip: str = '', data: Optional[Dict] = None) -> bool:
        try:
            from api.security.services import SecurityAuditService
            SecurityAuditService.log(user=user, event=event_type, ip=ip, data=data or {})
            return True
        except (ImportError, Exception):
            return False


class KYCAdapter(BaseAdapter):
    """CMS → api.kyc interface."""

    _system_name = 'api.kyc'

    @classmethod
    def _check_available(cls):
        import api.kyc  # noqa

    @classmethod
    def is_verified(cls, user) -> bool:
        """Check if user has completed KYC verification."""
        try:
            from api.kyc.models import KYCVerification
            return KYCVerification.objects.filter(user=user, status='approved').exists()
        except ImportError:
            return True  # assume verified if KYC system not installed
        except Exception:
            return False

    @classmethod
    def get_status(cls, user) -> str:
        """Return KYC status: 'approved', 'pending', 'rejected', 'not_started'."""
        try:
            from api.kyc.models import KYCVerification
            kyc = KYCVerification.objects.filter(user=user).order_by('-created_at').first()
            return kyc.status if kyc else 'not_started'
        except ImportError:
            return 'approved'
        except Exception:
            return 'unknown'

    @classmethod
    def requires_kyc_for_withdrawal(cls, amount_usd: float) -> bool:
        """Check platform config: does this withdrawal amount require KYC?"""
        try:
            from api.kyc.models import KYCConfig
            config = KYCConfig.objects.first()
            threshold = getattr(config, 'withdrawal_threshold_usd', 50)
            return amount_usd >= threshold
        except (ImportError, Exception):
            return amount_usd >= 50  # safe default


class ProxyAdapter(BaseAdapter):
    """CMS → api.proxy_intelligence interface."""

    _system_name = 'api.proxy_intelligence'

    @classmethod
    def _check_available(cls):
        import api.proxy_intelligence  # noqa

    @classmethod
    def analyze_ip(cls, ip_address: str) -> Dict:
        """
        Analyze an IP address.
        Returns {'country': str, 'is_proxy': bool, 'is_vpn': bool, 'is_tor': bool, 'risk_score': float}
        """
        try:
            from api.proxy_intelligence.services import ProxyIntelligenceService
            return ProxyIntelligenceService.analyze(ip=ip_address) or {
                'country': '', 'is_proxy': False, 'is_vpn': False, 'is_tor': False, 'risk_score': 0.0
            }
        except ImportError:
            return {'country': '', 'is_proxy': False, 'is_vpn': False, 'is_tor': False, 'risk_score': 0.0}
        except Exception as e:
            logger.debug("[CMS→Proxy] analyze_ip failed: %s", e)
            return {'country': '', 'is_proxy': False, 'is_vpn': False, 'is_tor': False, 'risk_score': 0.0}

    @classmethod
    def get_country(cls, ip_address: str) -> str:
        """Fast country lookup for targeting/personalization."""
        result = cls.analyze_ip(ip_address)
        return result.get('country', '')
