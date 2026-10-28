# api/referral/services/ReferralFraudService.py
# Fraud detection: self-referral, device match, IP match, velocity, blacklist
# ============================================================

from datetime import timedelta
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class ReferralFraudService:
    """
    Fraud detection engine।
    Multiple rule checks → fraud score → action।
    """

    MAX_FRAUD_SCORE = 100
    BLOCK_THRESHOLD = 70       # Score >= 70 → block
    HOLD_THRESHOLD = 40        # Score >= 40 → hold commission
    FLAG_THRESHOLD = 20        # Score >= 20 → flag

    @staticmethod
    def check_signup(
        new_user,
        referrer,
        new_user_ip: str = None,
        referrer_ip: str = None,
        device_fingerprint: str = None,
        user_agent: str = None,
    ) -> dict:
        """
        Signup fraud check।
        সব active rules apply করো।
        Returns fraud result dict।
        """
        from api.referral.models import ReferralFraudRule

        rules = ReferralFraudRule.objects.filter(is_active=True).order_by(
            '-priority'
        )

        total_score = 0
        flags = {}
        evidence = {
            'new_user_ip': new_user_ip,
            'referrer_ip': referrer_ip,
            'device_fingerprint': device_fingerprint,
        }
        action = 'allow'
        triggered_actions = []

        for rule in rules:
            triggered, score, detail = ReferralFraudService._check_rule(
                rule=rule,
                new_user=new_user,
                referrer=referrer,
                new_user_ip=new_user_ip,
                referrer_ip=referrer_ip,
                device_fingerprint=device_fingerprint,
            )

            if triggered:
                total_score = min(
                    ReferralFraudService.MAX_FRAUD_SCORE,
                    total_score + rule.fraud_score_points
                )
                flags[rule.rule_type] = True
                evidence[rule.rule_type] = detail
                triggered_actions.append(rule.action)

                logger.warning(
                    f"Fraud rule triggered: {rule.rule_type} "
                    f"for {new_user.username} "
                    f"(score: +{rule.fraud_score_points})"
                )
            else:
                flags[rule.rule_type] = False

        # Determine final action based on highest priority triggered action
        if 'block' in triggered_actions or total_score >= ReferralFraudService.BLOCK_THRESHOLD:
            action = 'block'
        elif 'hold_commission' in triggered_actions or total_score >= ReferralFraudService.HOLD_THRESHOLD:
            action = 'hold_commission'
        elif 'flag' in triggered_actions or total_score >= ReferralFraudService.FLAG_THRESHOLD:
            action = 'flag'
        elif 'notify_admin' in triggered_actions:
            action = 'flag'
        else:
            action = 'allow'

        is_suspicious = action != 'allow'

        reason_parts = [
            k for k, v in flags.items() if v
        ]
        reason = ', '.join(reason_parts) if reason_parts else ''

        return {
            'is_suspicious': is_suspicious,
            'fraud_score': total_score,
            'action': action,
            'flags': flags,
            'evidence': evidence,
            'reason': reason,
        }

    @staticmethod
    def _check_rule(rule, new_user, referrer, new_user_ip, referrer_ip, device_fingerprint) -> tuple:
        """
        Single rule check।
        Returns (triggered: bool, score: int, detail: str)
        """
        rule_type = rule.rule_type

        if rule_type == 'self_refer':
            if new_user.id == referrer.id:
                return True, rule.fraud_score_points, 'Self-referral detected'

        elif rule_type == 'ip_match':
            if new_user_ip and referrer_ip and new_user_ip == referrer_ip:
                return True, rule.fraud_score_points, f'Same IP: {new_user_ip}'

        elif rule_type == 'ip_subnet_match':
            if new_user_ip and referrer_ip:
                # Compare first 3 octets (class C subnet)
                new_parts = new_user_ip.split('.')[:3]
                ref_parts = referrer_ip.split('.')[:3]
                if new_parts == ref_parts and new_user_ip != referrer_ip:
                    return (
                        True,
                        rule.fraud_score_points,
                        f'Same subnet: {".".join(new_parts)}.*'
                    )

        elif rule_type == 'device_match':
            if device_fingerprint:
                from api.referral.models import Referral
                from django.db.models import Q
                # Check if device fingerprint was used by referrer recently
                # This requires device fingerprint to be stored on Referral or User
                # We check via a cache-based mechanism
                from django.core.cache import cache
                cache_key = f"ref_device:{referrer.id}:{device_fingerprint}"
                if cache.get(cache_key):
                    return (
                        True,
                        rule.fraud_score_points,
                        f'Device fingerprint match: {device_fingerprint[:20]}...'
                    )
                # Store referrer's device
                cache.set(
                    f"ref_device:{new_user.id}:{device_fingerprint}",
                    1,
                    timeout=86400 * 30
                )

        elif rule_type == 'velocity':
            # Too many referrals from referrer in time window
            from api.referral.models import Referral
            cutoff = timezone.now() - timedelta(
                minutes=rule.time_window_minutes
            )
            recent_count = Referral.objects.filter(
                referrer=referrer,
                created_at__gte=cutoff,
            ).count()
            if recent_count >= rule.threshold:
                return (
                    True,
                    rule.fraud_score_points,
                    f'Velocity: {recent_count} refs in {rule.time_window_minutes}min'
                )

        elif rule_type == 'new_account':
            # New user account created very recently (within 1 hour)
            if new_user.date_joined:
                age_minutes = (
                    timezone.now() - new_user.date_joined
                ).total_seconds() / 60
                if age_minutes < 60:
                    return (
                        True,
                        rule.fraud_score_points,
                        f'New account: {int(age_minutes)}min old'
                    )

        elif rule_type == 'blacklisted':
            if new_user_ip:
                result = ReferralFraudService._check_blacklist(
                    ip=new_user_ip,
                    email=getattr(new_user, 'email', ''),
                )
                if result['is_blacklisted']:
                    return (
                        True,
                        rule.fraud_score_points,
                        f"Blacklist match: {result['pattern_type']}={result['value']}"
                    )

        elif rule_type == 'email_domain':
            email = getattr(new_user, 'email', '')
            if email:
                domain = email.split('@')[-1].lower()
                suspicious_domains = [
                    'tempmail.com', 'throwaway.email', 'guerrillamail.com',
                    'mailinator.com', 'yopmail.com', '10minutemail.com',
                    'trashmail.com', 'sharklasers.com', 'guerrillamailblock.com',
                ]
                if domain in suspicious_domains:
                    return (
                        True,
                        rule.fraud_score_points,
                        f'Suspicious email domain: {domain}'
                    )

        return False, 0, ''

    @staticmethod
    def _check_blacklist(ip: str = None, email: str = None) -> dict:
        """IP বা email blacklist এ আছে কিনা check করো।"""
        from api.referral.models import ReferralBlacklist

        if ip:
            entry = ReferralBlacklist.objects.filter(
                pattern_type='ip',
                pattern_value=ip,
                is_active=True,
            ).first()
            if entry:
                entry.record_hit()
                return {'is_blacklisted': True, 'pattern_type': 'ip', 'value': ip}

        if email:
            # Exact email match
            entry = ReferralBlacklist.objects.filter(
                pattern_type='email',
                pattern_value__iexact=email,
                is_active=True,
            ).first()
            if entry:
                entry.record_hit()
                return {'is_blacklisted': True, 'pattern_type': 'email', 'value': email}

            # Domain match
            if '@' in email:
                domain = email.split('@')[-1].lower()
                entry = ReferralBlacklist.objects.filter(
                    pattern_type='email_domain',
                    pattern_value__iexact=domain,
                    is_active=True,
                ).first()
                if entry:
                    entry.record_hit()
                    return {
                        'is_blacklisted': True,
                        'pattern_type': 'email_domain',
                        'value': domain
                    }

        return {'is_blacklisted': False}

    @staticmethod
    def scan_existing_referrals() -> dict:
        """
        Existing referrals এর fraud scan।
        fraud_scan_tasks.py Celery task দিয়ে daily call করা হয়।
        """
        from api.referral.models import Referral, SuspiciousReferral

        # Unscanned non-suspicious referrals
        referrals = Referral.objects.filter(
            is_suspicious=False,
            suspicious_referral__isnull=True,
        ).select_related('referrer', 'referred_user').order_by('-created_at')[:500]

        flagged = 0
        for referral in referrals:
            result = ReferralFraudService.check_signup(
                new_user=referral.referred_user,
                referrer=referral.referrer,
                new_user_ip=referral.registration_ip,
                referrer_ip=referral.referrer_ip,
            )

            if result['is_suspicious']:
                referral.is_suspicious = True
                referral.suspicious_reason = result['reason']
                referral.save(update_fields=['is_suspicious', 'suspicious_reason'])

                SuspiciousReferral.objects.get_or_create(
                    referral=referral,
                    defaults={
                        'flags': result['flags'],
                        'fraud_score': result['fraud_score'],
                        'evidence': result['evidence'],
                    }
                )
                flagged += 1

        logger.info(f"Fraud scan: {len(referrals)} checked, {flagged} flagged")
        return {'scanned': len(referrals), 'flagged': flagged}

    @staticmethod
    def add_to_blacklist(
        pattern_type: str,
        pattern_value: str,
        reason: str,
        admin_user,
        severity: str = 'high',
    ) -> dict:
        """Blacklist এ নতুন entry add করো।"""
        from api.referral.models import ReferralBlacklist

        entry, created = ReferralBlacklist.objects.get_or_create(
            pattern_type=pattern_type,
            pattern_value=pattern_value,
            defaults={
                'reason': reason,
                'created_by': admin_user,
                'severity': severity,
                'is_active': True,
            }
        )

        if not created:
            entry.is_active = True
            entry.reason = reason
            entry.save(update_fields=['is_active', 'reason'])

        return {
            'success': True,
            'entry_id': entry.id,
            'created': created,
        }