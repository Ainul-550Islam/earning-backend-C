# api/referral/sanctions.py
# Referral sanctions — blacklist management, blocked countries/IPs,
# suspicious device fingerprints, banned email domains
# World-class feature: CPAlead blocks fraud traffic regions
# ============================================================

import re
import logging
from typing import Dict, List, Optional
from django.utils import timezone
from api.referral.models.fraud import ReferralBlacklist

logger = logging.getLogger(__name__)

# ── Known high-fraud countries/regions (ISO 3166-1 alpha-2) ──────────────────
# These are screened but NOT auto-blocked — flagged for review
HIGH_RISK_COUNTRIES = {'NG', 'GH', 'PK', 'VN', 'ID', 'PH'}

# ── Disposable email domains ──────────────────────────────────────────────────
DISPOSABLE_EMAIL_DOMAINS = {
    'mailinator.com', 'guerrillamail.com', 'tempmail.com', 'throwam.com',
    '10minutemail.com', 'sharklasers.com', 'guerrillamailblock.com',
    'grr.la', 'guerrillamail.info', 'trashmail.com', 'yopmail.com',
    'getairmail.com', 'mailnull.com', 'spamgourmet.com', 'maildrop.cc',
    'spamgourmet.net', 'spamgourmet.org', 'throwam.com', 'fakeinbox.com',
    'dispostable.com', 'spaml.de', 'trashmail.at', 'trashmail.io',
}


class SanctionsChecker:
    """
    Checks referral participants against sanctions, blacklists, and risk rules.
    Used in fraud detection before processing referrals.
    """

    @staticmethod
    def check_ip(ip: str) -> Dict:
        """
        Check if an IP is blacklisted or high-risk.
        Returns {'allowed': bool, 'risk_level': str, 'reasons': []}
        """
        from api.referral.models import ReferralBlacklist

        reasons = []
        risk_level = 'low'

        if not ip:
            return {'allowed': True, 'risk_level': risk_level, 'reasons': reasons}

        # Check DB blacklist
        blacklist_entry = ReferralBlacklist.objects.filter(
            pattern_type='ip',
            pattern_value=ip,
            is_active=True,
        ).first()

        if blacklist_entry:
            blacklist_entry.hit_count = blacklist_entry.hit_count + 1
            blacklist_entry.save(update_fields=['hit_count'])
            reasons.append(f'IP blacklisted: {blacklist_entry.reason}')
            risk_level = blacklist_entry.severity
            if blacklist_entry.severity == 'critical':
                return {'allowed': False, 'risk_level': 'critical', 'reasons': reasons}

        return {'allowed': True, 'risk_level': risk_level, 'reasons': reasons}

    @staticmethod
    def check_email(email: str) -> Dict:
        """
        Check if an email is sanctioned.
        Checks: disposable domains, blacklisted emails.
        """
        from api.referral.models import ReferralBlacklist

        reasons = []
        risk_level = 'low'

        if not email:
            return {'allowed': True, 'risk_level': risk_level, 'reasons': reasons}

        email_lower = email.lower()
        domain = email_lower.split('@')[-1] if '@' in email_lower else ''

        # Disposable domain check
        if domain in DISPOSABLE_EMAIL_DOMAINS:
            reasons.append(f'Disposable email domain: {domain}')
            risk_level = 'high'

        # DB blacklist
        blacklist_entry = ReferralBlacklist.objects.filter(
            pattern_type__in=['email', 'email_domain'],
            is_active=True,
        ).filter(
            __import__('django.db.models', fromlist=['Q']).Q(pattern_value=email_lower)
            | __import__('django.db.models', fromlist=['Q']).Q(pattern_value=domain)
        ).first()

        if blacklist_entry:
            reasons.append(f'Email/domain blacklisted: {blacklist_entry.reason}')
            risk_level = blacklist_entry.severity
            if blacklist_entry.severity == 'critical':
                return {'allowed': False, 'risk_level': 'critical', 'reasons': reasons}

        return {'allowed': len(reasons) == 0, 'risk_level': risk_level, 'reasons': reasons}

    @staticmethod
    def check_device_fingerprint(fingerprint: str) -> Dict:
        """Check if a device fingerprint is blacklisted."""
        from api.referral.models import ReferralBlacklist

        if not fingerprint:
            return {'allowed': True, 'risk_level': 'low', 'reasons': []}

        entry = ReferralBlacklist.objects.filter(
            pattern_type='device_fingerprint',
            pattern_value=fingerprint,
            is_active=True,
        ).first()

        if entry:
            return {
                'allowed': entry.severity != 'critical',
                'risk_level': entry.severity,
                'reasons': [f'Device fingerprint blacklisted: {entry.reason}'],
            }

        return {'allowed': True, 'risk_level': 'low', 'reasons': []}

    @staticmethod
    def check_user(user) -> Dict:
        """
        Full sanctions check for a user before processing referral.
        """
        reasons = []
        risk_level = 'low'
        allowed = True

        # Check email
        email = getattr(user, 'email', '') or ''
        email_check = SanctionsChecker.check_email(email)
        if not email_check['allowed']:
            allowed = False
            risk_level = email_check['risk_level']
            reasons.extend(email_check['reasons'])

        # Check if user is banned/inactive
        if not getattr(user, 'is_active', True):
            reasons.append('User account is inactive')
            allowed = False
            risk_level = 'critical'

        return {
            'allowed': allowed,
            'risk_level': risk_level,
            'reasons': reasons,
        }

    @staticmethod
    def full_check(new_user, referrer, ip: str = '',
                   device_fp: str = '') -> Dict:
        """
        Complete sanctions check for a referral attempt.
        Combines all individual checks.
        """
        all_reasons = []
        max_risk = 'low'
        allowed = True

        risk_order = {'low': 0, 'medium': 1, 'high': 2, 'critical': 3}

        for check in [
            SanctionsChecker.check_user(new_user),
            SanctionsChecker.check_user(referrer),
            SanctionsChecker.check_ip(ip) if ip else {'allowed': True, 'risk_level': 'low', 'reasons': []},
            SanctionsChecker.check_device_fingerprint(device_fp) if device_fp else {'allowed': True, 'risk_level': 'low', 'reasons': []},
        ]:
            if not check['allowed']:
                allowed = False
            if risk_order.get(check['risk_level'], 0) > risk_order.get(max_risk, 0):
                max_risk = check['risk_level']
            all_reasons.extend(check['reasons'])

        return {
            'allowed': allowed,
            'risk_level': max_risk,
            'reasons': all_reasons,
            'is_high_risk': max_risk in ('high', 'critical'),
        }


class BlacklistManager:
    """Manages the referral blacklist."""

    @staticmethod
    def add(pattern_type: str, pattern_value: str, severity: str = 'high',
            reason: str = '', added_by=None) -> 'ReferralBlacklist':
        from api.referral.models import ReferralBlacklist
        entry, created = ReferralBlacklist.objects.update_or_create(
            pattern_type=pattern_type,
            pattern_value=pattern_value.lower().strip(),
            defaults={
                'severity': severity,
                'reason': reason,
                'is_active': True,
                'created_by': added_by,
            }
        )
        logger.warning(
            f'[Sanctions] Blacklist {"added" if created else "updated"}: '
            f'{pattern_type}={pattern_value} severity={severity}'
        )
        return entry

    @staticmethod
    def remove(pattern_type: str, pattern_value: str) -> bool:
        from api.referral.models import ReferralBlacklist
        updated = ReferralBlacklist.objects.filter(
            pattern_type=pattern_type,
            pattern_value=pattern_value.lower().strip(),
        ).update(is_active=False)
        return updated > 0

    @staticmethod
    def bulk_add_ips(ips: List[str], reason: str = 'bulk_add',
                     added_by=None, severity: str = 'high') -> int:
        """Bulk add IPs to blacklist."""
        added = 0
        for ip in ips:
            try:
                BlacklistManager.add('ip', ip, severity=severity,
                                     reason=reason, added_by=added_by)
                added += 1
            except Exception as e:
                logger.error(f'[Sanctions] bulk_add_ips failed for {ip}: {e}')
        return added

    @staticmethod
    def get_all_active(pattern_type: str = None) -> list:
        from api.referral.models import ReferralBlacklist
        qs = ReferralBlacklist.objects.filter(is_active=True)
        if pattern_type:
            qs = qs.filter(pattern_type=pattern_type)
        return list(qs.values('id', 'pattern_type', 'pattern_value',
                               'severity', 'reason', 'hit_count'))


# ── Re-export for type hints ──────────────────────────────────────────────────
from typing import List  # noqa: E402