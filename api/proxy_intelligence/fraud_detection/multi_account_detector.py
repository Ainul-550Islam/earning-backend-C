"""
Multi-Account Fraud Detector
=============================
Detects users creating multiple accounts from the same IP or device.
"""
import logging
from django.conf import settings
from django.db.models import Count

logger = logging.getLogger(__name__)


class MultiAccountDetector:
    """
    Detects multi-account fraud by linking accounts via shared identifiers:
    - Same IP address
    - Same device fingerprint
    - Similar behavioral patterns
    """

    def __init__(self, user, tenant=None):
        self.user = user
        self.tenant = tenant

    def check_ip_overlap(self, ip_address: str, threshold: int = 2) -> dict:
        """Find other users who have used this IP."""
        from ..models import IPIntelligence, MultiAccountLink
        User = settings.AUTH_USER_MODEL

        # Find accounts with same IP from VPN/proxy logs
        from ..models import VPNDetectionLog, ProxyDetectionLog

        vpn_users = set(
            VPNDetectionLog.objects.filter(ip_address=ip_address)
            .exclude(user=self.user)
            .values_list('user_id', flat=True)
        )
        proxy_users = set(
            ProxyDetectionLog.objects.filter(ip_address=ip_address)
            .exclude(user=self.user)
            .values_list('user_id', flat=True)
        )
        linked_user_ids = vpn_users | proxy_users

        if len(linked_user_ids) >= threshold:
            # Create links
            for uid in list(linked_user_ids)[:10]:  # max 10 links per check
                try:
                    from django.contrib.auth import get_user_model
                    UserModel = get_user_model()
                    linked = UserModel.objects.get(pk=uid)
                    MultiAccountLink.objects.get_or_create(
                        primary_user=self.user,
                        linked_user=linked,
                        link_type='same_ip',
                        defaults={
                            'shared_identifier': ip_address,
                            'confidence_score': 0.8,
                            'is_suspicious': True,
                            'tenant': self.tenant,
                        }
                    )
                except Exception as e:
                    logger.debug(f"Could not create multi-account link: {e}")

        return {
            'suspicious': len(linked_user_ids) >= threshold,
            'linked_accounts': len(linked_user_ids),
            'ip_address': ip_address,
        }

    def check_device_overlap(self, fingerprint_hash: str) -> dict:
        """Find other users with the same device fingerprint."""
        from ..models import DeviceFingerprint, MultiAccountLink

        other_users = (
            DeviceFingerprint.objects.filter(fingerprint_hash=fingerprint_hash)
            .exclude(user=self.user)
            .values_list('user_id', flat=True)
            .distinct()
        )
        linked_count = len(list(other_users))

        if linked_count > 0:
            from django.contrib.auth import get_user_model
            UserModel = get_user_model()
            for uid in list(other_users)[:5]:
                try:
                    linked = UserModel.objects.get(pk=uid)
                    MultiAccountLink.objects.get_or_create(
                        primary_user=self.user,
                        linked_user=linked,
                        link_type='same_device',
                        defaults={
                            'shared_identifier': fingerprint_hash[:20],
                            'confidence_score': 0.95,
                            'is_suspicious': True,
                            'tenant': self.tenant,
                        }
                    )
                except Exception as e:
                    logger.debug(f"Device overlap link error: {e}")

        return {
            'suspicious': linked_count > 0,
            'linked_accounts': linked_count,
            'fingerprint': fingerprint_hash[:12] + '...',
        }

    def get_risk_assessment(self, ip_address: str = '', fingerprint_hash: str = '') -> dict:
        """Full multi-account risk assessment."""
        results = {}
        risk_score = 0

        if ip_address:
            ip_result = self.check_ip_overlap(ip_address)
            results['ip_overlap'] = ip_result
            if ip_result['suspicious']:
                risk_score += 30

        if fingerprint_hash:
            device_result = self.check_device_overlap(fingerprint_hash)
            results['device_overlap'] = device_result
            if device_result['suspicious']:
                risk_score += 40

        return {
            'user_id': self.user.pk,
            'multi_account_risk_score': min(risk_score, 100),
            'multi_account_detected': risk_score > 0,
            'checks': results,
        }
